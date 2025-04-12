package main

import (
	"log/slog"
	"net/http"
	"os"

	"github.com/hsin19/Finchie/services/ledger-svc/internal/statements"
)

func main() {
	initLogger()
	statementsRepo := statements.NewRepoFromEnv()
	statementsManager := statements.StatementManager{
		Service: statements.NewService(statementsRepo),
		Repo:    statementsRepo,
	}

	http.HandleFunc("/api/statements", statementsManager.StatementsHandler)
	slog.Info("Server running", "port", ":8080")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		slog.Error("Server failed", "error", err)
		os.Exit(1)
	}
}

func initLogger() {
	isLocal := os.Getenv("IS_LOCAL") == "true"

	var handler slog.Handler
	if isLocal {
		handler = slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelDebug})
	} else {
		handler = slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo})
	}

	slog.SetDefault(slog.New(handler))
	slog.Debug("Logger initialized", "isLocal", isLocal)
}
