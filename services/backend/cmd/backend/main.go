package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/labstack/echo/v5"
	"github.com/labstack/echo/v5/middleware"
	"github.com/riverqueue/river"
	"github.com/riverqueue/river/riverdriver/riverpgxv5"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	"github.com/hsin19/finchie/services/backend/internal/api"
	"github.com/hsin19/finchie/services/backend/internal/config"
	"github.com/hsin19/finchie/services/backend/internal/db"
	parserv1 "github.com/hsin19/finchie/services/backend/internal/gen/finchie/parser/v1"
	"github.com/hsin19/finchie/services/backend/internal/ingest"
	"github.com/hsin19/finchie/services/backend/internal/web"
)

func main() {
	if len(os.Args) > 1 && os.Args[1] == "healthcheck" {
		addr := os.Getenv("BACKEND_HTTP_ADDR")
		if addr == "" {
			addr = ":8080"
		}
		if err := healthcheck(addr); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		return
	}
	if err := run(); err != nil {
		slog.Error("backend stopped", "error", err)
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}
	logger := newLogger(cfg.LogFormat)
	slog.SetDefault(logger)

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	pool, err := pgxpool.New(ctx, cfg.DatabaseURL)
	if err != nil {
		return fmt.Errorf("connect database: %w", err)
	}
	defer pool.Close()
	if err := db.Migrate(ctx, pool); err != nil {
		return err
	}

	// The parser is internal and stateless (ADR 0002): plaintext on the private network.
	limit := grpc.WithDefaultCallOptions(grpc.MaxCallSendMsgSize(int(cfg.MaxUploadBytes()) + 1<<20))
	conn, err := grpc.NewClient(cfg.ParserAddr, grpc.WithTransportCredentials(insecure.NewCredentials()), limit)
	if err != nil {
		return fmt.Errorf("parser client: %w", err)
	}
	defer func() {
		if err := conn.Close(); err != nil {
			slog.Warn("closing parser connection", "error", err)
		}
	}()

	workers := river.NewWorkers()
	river.AddWorker(workers, ingest.NewWorker(pool, parserv1.NewParserServiceClient(conn), cfg.ParseTimeout))
	jobs, err := river.NewClient(riverpgxv5.New(pool), &river.Config{
		Queues:  map[string]river.QueueConfig{river.QueueDefault: {MaxWorkers: cfg.ParseConcurrency}},
		Workers: workers,
		Logger:  logger,
	})
	if err != nil {
		return fmt.Errorf("job client: %w", err)
	}
	if err := jobs.Start(ctx); err != nil {
		return fmt.Errorf("start jobs: %w", err)
	}

	e := echo.New()
	e.Logger = logger
	e.Use(middleware.Recover(), middleware.RequestLogger(), middleware.BodyLimit(cfg.MaxUploadBytes()+1<<20))
	e.GET("/healthz", func(c *echo.Context) error {
		if err := pool.Ping(c.Request().Context()); err != nil {
			return c.String(http.StatusServiceUnavailable, "database unreachable")
		}
		return c.String(http.StatusOK, "ok")
	})
	api.RegisterHandlers(e, api.NewStrictHandler(api.NewServer(pool, jobs, cfg.MaxUploadBytes()), nil))
	web.Register(e)

	slog.Info("listening", "addr", cfg.HTTPAddr, "parser", cfg.ParserAddr)
	serveErr := echo.StartConfig{Address: cfg.HTTPAddr, HideBanner: true, GracefulTimeout: 10 * time.Second}.Start(ctx, e)

	stopCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if err := jobs.Stop(stopCtx); err != nil {
		slog.Warn("jobs did not stop cleanly", "error", err)
	}
	if serveErr != nil && !errors.Is(serveErr, http.ErrServerClosed) {
		return fmt.Errorf("http server: %w", serveErr)
	}
	return nil
}

func newLogger(format string) *slog.Logger {
	if format == "text" {
		return slog.New(slog.NewTextHandler(os.Stdout, nil))
	}
	return slog.New(slog.NewJSONHandler(os.Stdout, nil))
}
