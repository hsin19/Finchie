// Package web serves the browser app (web/ in the repository) from files embedded at build time.
// The app is a single-page app: any path that is not a file gets its HTML shell, and its router
// takes over from there.
package web

import (
	"embed"
	"io/fs"
	"net/http"
	"path"
	"strings"

	"github.com/labstack/echo/v5"
)

//go:embed all:dist
var dist embed.FS

// shell is the page adapter-static writes for routes it did not prerender.
const shell = "200.html"

// Register serves the app for GET requests that no other route claimed. Unknown /api paths stay
// 404 rather than turning into HTML.
func Register(e *echo.Echo) {
	files, err := fs.Sub(dist, "dist")
	if err != nil {
		panic(err) // the embed directive guarantees the directory
	}
	e.GET("/*", handler(files))
}

func handler(files fs.FS) echo.HandlerFunc {
	return func(c *echo.Context) error {
		name := strings.TrimPrefix(path.Clean("/"+c.Request().URL.Path), "/")
		if name == "api" || strings.HasPrefix(name, "api/") {
			return echo.ErrNotFound
		}
		if !isFile(files, name) {
			// A missing asset is a 404; anything else is a client-side route.
			if path.Ext(name) != "" {
				return echo.ErrNotFound
			}
			name = shell
		}
		if !isFile(files, name) {
			return c.String(http.StatusNotFound, "the web app is not built into this binary: run `task backend:web` and rebuild")
		}

		header := c.Response().Header()
		if strings.HasPrefix(name, "_app/immutable/") {
			header.Set("Cache-Control", "public, max-age=31536000, immutable")
		} else {
			header.Set("Cache-Control", "no-cache")
		}
		return c.FileFS(name, files)
	}
}

func isFile(files fs.FS, name string) bool {
	if name == "" {
		return false
	}
	info, err := fs.Stat(files, name)
	return err == nil && info.Mode().IsRegular()
}
