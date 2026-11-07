package telemetry

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/labstack/echo/v5"
	"go.opentelemetry.io/otel"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/sdk/trace/tracetest"
)

func TestRequestsAreTracedByRoute(t *testing.T) {
	recorder := tracetest.NewSpanRecorder()
	provider := sdktrace.NewTracerProvider(sdktrace.WithSpanProcessor(recorder))
	previous := otel.GetTracerProvider()
	otel.SetTracerProvider(provider)
	t.Cleanup(func() { otel.SetTracerProvider(previous) })

	e := echo.New()
	e.Use(Route())
	ok := func(c *echo.Context) error { return c.String(http.StatusOK, "ok") }
	e.GET("/api/statements/:id", ok)
	e.GET(HealthPath, ok)
	server := Handler(e)

	for _, path := range []string{"/api/statements/42", HealthPath} {
		server.ServeHTTP(httptest.NewRecorder(), httptest.NewRequestWithContext(t.Context(), http.MethodGet, path, nil))
	}

	spans := recorder.Ended()
	if len(spans) != 1 {
		t.Fatalf("spans = %d, want 1 (the health check is not traced)", len(spans))
	}
	if name := spans[0].Name(); name != "GET /api/statements/:id" {
		t.Fatalf("span name = %q, want the route, not the path", name)
	}
}
