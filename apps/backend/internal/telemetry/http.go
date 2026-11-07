package telemetry

import (
	"net/http"

	"github.com/labstack/echo/v5"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
)

// HealthPath is left out of traces: Docker and the monitoring probe call it every few seconds.
const HealthPath = "/healthz"

// Handler wraps the whole server: a span and the http.server metrics for every request but the health
// check. It runs before Echo routes the request, so Route fills in the route.
func Handler(h http.Handler) http.Handler {
	return otelhttp.NewHandler(h, "http.server", otelhttp.WithFilter(func(r *http.Request) bool {
		return r.URL.Path != HealthPath
	}))
}

// Route names the request's span after the route Echo matched ("GET /api/statements/:id") and adds
// it to the request's metrics, so neither is split by every ID.
func Route() echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c *echo.Context) error {
			if route := c.Path(); route != "" {
				request := c.Request()
				span := trace.SpanFromContext(request.Context())
				span.SetName(request.Method + " " + route)
				span.SetAttributes(attribute.String("http.route", route))
				if labeler, ok := otelhttp.LabelerFromContext(request.Context()); ok {
					labeler.Add(attribute.String("http.route", route))
				}
			}
			return next(c)
		}
	}
}
