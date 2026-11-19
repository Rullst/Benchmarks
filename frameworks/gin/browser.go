// The browser routes: /form, /login and /me (docs/v3-spec.md, sections 4-6).
//
// Both are middleware of this route group only, so the other routes keep
// their stack. CSRF: Go's http.CrossOriginProtection, called through its
// Check method, so the forms carry no token. Sessions: gin-contrib/sessions
// with its cookie store (a signed cookie).
package main

import (
	"crypto/rand"
	"errors"
	"log"
	"net/http"

	"github.com/gin-contrib/sessions"
	"github.com/gin-contrib/sessions/cookie"
	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
)

const userIDKey = "userId"

// User is a row of the phase-2 users table.
type User struct {
	ID             int32  `gorm:"primaryKey"`
	Username       string `gorm:"column:username"`
	DisplayName    string `gorm:"column:display_name"`
	PasswordBcrypt string `gorm:"column:password_bcrypt"`
}

func (User) TableName() string {
	return "users"
}

// FormInput is POST /form's fields; ShouldBind validates the tags (400).
type FormInput struct {
	Name         string `form:"name" binding:"required,max=64"`
	RandomNumber int    `form:"randomNumber" binding:"required,min=1,max=10000"`
}

type LoginInput struct {
	Username string `form:"username" binding:"required"`
	Password string `form:"password" binding:"required"`
}

func browserRoutes(router *gin.Engine, db *gorm.DB) {
	// The cookie store's authentication (HMAC) key. One process serves every
	// request, so a key drawn at start-up signs and checks every cookie.
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		log.Fatalf("session key: %v", err)
	}
	browser := router.Group("")
	browser.Use(crossOriginProtection(http.NewCrossOriginProtection()))
	browser.Use(sessions.Sessions("session", cookie.NewStore(key)))

	browser.GET("/form", func(c *gin.Context) {
		c.HTML(http.StatusOK, "form.html", nil)
	})

	browser.POST("/form", func(c *gin.Context) {
		var input FormInput
		if err := c.ShouldBind(&input); err != nil {
			c.Status(http.StatusBadRequest)
			return
		}
		c.HTML(http.StatusOK, "form_result.html", gin.H{"name": input.Name, "randomNumber": input.RandomNumber})
	})

	browser.GET("/login", func(c *gin.Context) {
		c.HTML(http.StatusOK, "login.html", nil)
	})

	// The bcrypt hash of users checked with golang.org/x/crypto/bcrypt, then
	// the user's id in the session (the cookie is signed when saved).
	browser.POST("/login", func(c *gin.Context) {
		var input LoginInput
		if err := c.ShouldBind(&input); err != nil {
			c.Status(http.StatusBadRequest)
			return
		}
		var user User
		err := db.WithContext(c.Request.Context()).Select("id", "password_bcrypt").
			Where("username = ?", input.Username).Take(&user).Error
		if errors.Is(err, gorm.ErrRecordNotFound) {
			c.Status(http.StatusUnauthorized)
			return
		}
		if err != nil {
			c.Status(http.StatusInternalServerError)
			return
		}
		if bcrypt.CompareHashAndPassword([]byte(user.PasswordBcrypt), []byte(input.Password)) != nil {
			c.Status(http.StatusUnauthorized)
			return
		}
		session := sessions.Default(c)
		session.Set(userIDKey, int(user.ID))
		if err := session.Save(); err != nil {
			c.Status(http.StatusInternalServerError)
			return
		}
		c.Redirect(http.StatusSeeOther, "/me")
	})

	// The session's signature is checked by the store; the user's row is read on every request.
	browser.GET("/me", func(c *gin.Context) {
		id, ok := sessions.Default(c).Get(userIDKey).(int)
		if !ok {
			c.Status(http.StatusUnauthorized)
			return
		}
		var user User
		err := db.WithContext(c.Request.Context()).Select("id", "username", "display_name").Take(&user, id).Error
		if errors.Is(err, gorm.ErrRecordNotFound) {
			c.Status(http.StatusUnauthorized)
			return
		}
		if err != nil {
			c.Status(http.StatusInternalServerError)
			return
		}
		c.JSON(http.StatusOK, gin.H{"id": user.ID, "username": user.Username, "displayName": user.DisplayName})
	})
}

// crossOriginProtection runs Go's CSRF check as Gin middleware: an unsafe
// request whose Sec-Fetch-Site (or, without it, Origin compared with Host)
// shows another origin is refused with 403, as the Handler wrapper does.
func crossOriginProtection(protection *http.CrossOriginProtection) gin.HandlerFunc {
	return func(c *gin.Context) {
		if err := protection.Check(c.Request); err != nil {
			c.AbortWithStatus(http.StatusForbidden)
			return
		}
		c.Next()
	}
}
