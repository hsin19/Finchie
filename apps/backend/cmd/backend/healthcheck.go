package main

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"strconv"
	"time"
)

// healthcheck backs the container's HEALTHCHECK: the distroless image has no curl.
func healthcheck(addr string) error {
	_, portText, err := net.SplitHostPort(addr)
	if err != nil {
		return fmt.Errorf("parse address %q: %w", addr, err)
	}
	port, err := strconv.Atoi(portText)
	if err != nil {
		return fmt.Errorf("parse port %q: %w", portText, err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	// Always the local loopback; only the port comes from the environment.
	url := fmt.Sprintf("http://127.0.0.1:%d/healthz", port)
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil) //nolint:gosec // loopback only
	if err != nil {
		return fmt.Errorf("build request: %w", err)
	}
	response, err := http.DefaultClient.Do(request) //nolint:gosec // loopback only
	if err != nil {
		return fmt.Errorf("health request: %w", err)
	}
	defer func() { _ = response.Body.Close() }()
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("unhealthy: %s", response.Status)
	}
	return nil
}
