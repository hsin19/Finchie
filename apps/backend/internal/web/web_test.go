package web

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"testing/fstest"

	"github.com/labstack/echo/v5"
)

func TestHandlerServesFilesAndFallsBackToTheShell(t *testing.T) {
	e := echo.New()
	e.GET("/*", handler(fstest.MapFS{
		"200.html":                {Data: []byte("<html>shell</html>")},
		"robots.txt":              {Data: []byte("User-agent: *")},
		"_app/immutable/app.js":   {Data: []byte("export {}")},
		"_app/version.json":       {Data: []byte("{}")},
		"_app/immutable/nested/a": {Data: []byte("x")},
	}))

	cases := []struct {
		path, body, cache string
		status            int
	}{
		{"/", "<html>shell</html>", "no-cache", http.StatusOK},
		{"/statements/12", "<html>shell</html>", "no-cache", http.StatusOK},
		{"/robots.txt", "User-agent: *", "no-cache", http.StatusOK},
		{"/_app/immutable/app.js", "export {}", "public, max-age=31536000, immutable", http.StatusOK},
		{"/_app/immutable/missing.js", "", "", http.StatusNotFound},
		{"/api/unknown", "", "", http.StatusNotFound},
		{"/_app", "<html>shell</html>", "no-cache", http.StatusOK},
	}
	for _, tc := range cases {
		t.Run(tc.path, func(t *testing.T) {
			recorder := httptest.NewRecorder()
			e.ServeHTTP(recorder, httptest.NewRequestWithContext(t.Context(), http.MethodGet, tc.path, nil))
			if recorder.Code != tc.status {
				t.Fatalf("status = %d, want %d", recorder.Code, tc.status)
			}
			if tc.status != http.StatusOK {
				return
			}
			if got := recorder.Body.String(); got != tc.body {
				t.Errorf("body = %q, want %q", got, tc.body)
			}
			if got := recorder.Header().Get("Cache-Control"); got != tc.cache {
				t.Errorf("Cache-Control = %q, want %q", got, tc.cache)
			}
		})
	}
}

func TestHandlerExplainsAMissingBuild(t *testing.T) {
	e := echo.New()
	e.GET("/*", handler(fstest.MapFS{}))
	recorder := httptest.NewRecorder()
	e.ServeHTTP(recorder, httptest.NewRequestWithContext(t.Context(), http.MethodGet, "/", nil))
	if recorder.Code != http.StatusNotFound {
		t.Fatalf("status = %d", recorder.Code)
	}
}
