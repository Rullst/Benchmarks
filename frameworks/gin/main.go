// Gin: the suite's endpoints with GORM (pgx driver) and html/template.
package main

import (
	"errors"
	"log"
	"math/rand/v2"
	"net/http"
	"os"
	"slices"
	"sort"
	"strconv"

	"github.com/gin-gonic/gin"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

type World struct {
	ID           int32 `gorm:"primaryKey" json:"id"`
	RandomNumber int32 `gorm:"column:randomnumber" json:"randomNumber"`
}

func (World) TableName() string {
	return "world"
}

type Fortune struct {
	ID      int32  `gorm:"primaryKey"`
	Message string `gorm:"column:message"`
}

func (Fortune) TableName() string {
	return "fortune"
}

// WorldURI is the id of /world/:id; a non-integer id fails to bind (400).
type WorldURI struct {
	ID int32 `uri:"id"`
}

// WorldsQuery is GET /worlds' query string, with its defaults and ranges.
type WorldsQuery struct {
	Min   int `form:"min,default=1" binding:"min=1,max=10000"`
	Max   int `form:"max,default=10000" binding:"min=1,max=10000,gtefield=Min"`
	Limit int `form:"limit,default=20" binding:"min=1,max=100"`
	Page  int `form:"page,default=1" binding:"min=1,max=1000"`
}

// WorldUpdate is PUT /world/:id's JSON body: a JSON integer from 1 to 10000.
type WorldUpdate struct {
	RandomNumber *int32 `json:"randomNumber" binding:"required,min=1,max=10000"`
}

func envInt(name string, fallback int) int {
	if value, err := strconv.Atoi(os.Getenv(name)); err == nil && value > 0 {
		return value
	}
	return fallback
}

// queryCount is the queries parameter: an integer clamped to 1..500, otherwise 1.
func queryCount(value string) int {
	count, err := strconv.Atoi(value)
	if err != nil {
		return 1
	}
	return min(max(count, 1), 500)
}

func randomID() int32 {
	return rand.Int32N(10000) + 1
}

// newRandomNumber is a new random number, different from the current one so
// that every row is written.
func newRandomNumber(current int32) int32 {
	for {
		if value := randomID(); value != current {
			return value
		}
	}
}

func main() {
	db, err := gorm.Open(postgres.Open(os.Getenv("DATABASE_URL")), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Silent),
	})
	if err != nil {
		log.Fatalf("database: %v", err)
	}
	sqlDB, err := db.DB()
	if err != nil {
		log.Fatalf("database: %v", err)
	}
	// One pool for the process; database/sql keeps only 2 idle connections
	// unless told otherwise, so the idle limit matches the pool size.
	pool := envInt("DB_POOL_SIZE", 16)
	sqlDB.SetMaxOpenConns(pool)
	sqlDB.SetMaxIdleConns(pool)

	// gin.Default() without its Logger middleware.
	router := gin.New()
	router.Use(gin.Recovery())
	router.LoadHTMLGlob("templates/*")

	router.GET("/text", func(c *gin.Context) {
		c.String(http.StatusOK, "Hello World")
	})

	router.GET("/json", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"message": "Hello World"})
	})

	router.GET("/db-single", func(c *gin.Context) {
		var world World
		if err := db.WithContext(c.Request.Context()).Take(&world, 1).Error; err != nil {
			c.Status(http.StatusInternalServerError)
			return
		}
		c.JSON(http.StatusOK, world)
	})

	router.GET("/html", func(c *gin.Context) {
		c.HTML(http.StatusOK, "hello.html", gin.H{"name": "World"})
	})

	// One Take per random id.
	router.GET("/queries", func(c *gin.Context) {
		tx := db.WithContext(c.Request.Context())
		worlds := make([]World, queryCount(c.Query("queries")))
		for i := range worlds {
			if err := tx.Take(&worlds[i], randomID()).Error; err != nil {
				c.Status(http.StatusInternalServerError)
				return
			}
		}
		c.JSON(http.StatusOK, worlds)
	})

	// Each row is read with its own Take and given a new value; the UPDATEs
	// run in one transaction, in ascending id order, so concurrent requests
	// lock rows in the same order.
	router.GET("/updates", func(c *gin.Context) {
		tx := db.WithContext(c.Request.Context())
		ids := make([]int32, queryCount(c.Query("queries")))
		for i := range ids {
			ids[i] = randomID()
		}
		slices.Sort(ids)
		worlds := make([]World, len(ids))
		for i, id := range ids {
			if err := tx.Take(&worlds[i], id).Error; err != nil {
				c.Status(http.StatusInternalServerError)
				return
			}
			worlds[i].RandomNumber = newRandomNumber(worlds[i].RandomNumber)
		}
		err := tx.Transaction(func(tx *gorm.DB) error {
			for i := range worlds {
				if err := tx.Model(&worlds[i]).Update("randomnumber", worlds[i].RandomNumber).Error; err != nil {
					return err
				}
			}
			return nil
		})
		if err != nil {
			c.Status(http.StatusInternalServerError)
			return
		}
		c.JSON(http.StatusOK, worlds)
	})

	// Every fortune (no ORDER BY), plus one added here, sorted by message
	// (byte order of UTF-8, which is code-point order).
	router.GET("/fortunes", func(c *gin.Context) {
		var fortunes []Fortune
		if err := db.WithContext(c.Request.Context()).Find(&fortunes).Error; err != nil {
			c.Status(http.StatusInternalServerError)
			return
		}
		fortunes = append(fortunes, Fortune{ID: 0, Message: "Additional fortune added at request time."})
		sort.Slice(fortunes, func(i, j int) bool { return fortunes[i].Message < fortunes[j].Message })
		c.HTML(http.StatusOK, "fortunes.html", gin.H{"fortunes": fortunes})
	})

	router.GET("/world/:id", func(c *gin.Context) {
		var uri WorldURI
		if err := c.ShouldBindUri(&uri); err != nil {
			c.Status(http.StatusBadRequest)
			return
		}
		var world World
		if err := db.WithContext(c.Request.Context()).Take(&world, uri.ID).Error; err != nil {
			c.Status(statusOf(err))
			return
		}
		c.JSON(http.StatusOK, world)
	})

	// One query: filter, order and paginate in PostgreSQL.
	router.GET("/worlds", func(c *gin.Context) {
		var query WorldsQuery
		if err := c.ShouldBindQuery(&query); err != nil {
			c.Status(http.StatusBadRequest)
			return
		}
		worlds := []World{}
		err := db.WithContext(c.Request.Context()).
			Where("id BETWEEN ? AND ?", query.Min, query.Max).
			Order("id").Limit(query.Limit).Offset((query.Page - 1) * query.Limit).
			Find(&worlds).Error
		if err != nil {
			c.Status(http.StatusInternalServerError)
			return
		}
		c.JSON(http.StatusOK, worlds)
	})

	// The body is bound and validated (400) before the row is loaded, changed and saved.
	router.PUT("/world/:id", func(c *gin.Context) {
		var uri WorldURI
		var body WorldUpdate
		if err := c.ShouldBindUri(&uri); err != nil {
			c.Status(http.StatusBadRequest)
			return
		}
		if err := c.ShouldBindJSON(&body); err != nil {
			c.Status(http.StatusBadRequest)
			return
		}
		tx := db.WithContext(c.Request.Context())
		var world World
		if err := tx.Take(&world, uri.ID).Error; err != nil {
			c.Status(statusOf(err))
			return
		}
		world.RandomNumber = *body.RandomNumber
		if err := tx.Save(&world).Error; err != nil {
			c.Status(http.StatusInternalServerError)
			return
		}
		c.JSON(http.StatusOK, world)
	})

	browserRoutes(router, db)

	if err := router.Run(":" + strconv.Itoa(envInt("PORT", 8080))); err != nil {
		log.Fatal(err)
	}
}

// statusOf is 404 for a missing row, 500 for any other database error.
func statusOf(err error) int {
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return http.StatusNotFound
	}
	return http.StatusInternalServerError
}
