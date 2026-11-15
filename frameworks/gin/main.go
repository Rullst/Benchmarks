// Gin: the suite's four endpoints with GORM (pgx driver) and html/template.
package main

import (
	"log"
	"net/http"
	"os"
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

func envInt(name string, fallback int) int {
	if value, err := strconv.Atoi(os.Getenv(name)); err == nil && value > 0 {
		return value
	}
	return fallback
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

	if err := router.Run(":" + strconv.Itoa(envInt("PORT", 8080))); err != nil {
		log.Fatal(err)
	}
}
