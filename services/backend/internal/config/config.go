// Package config reads the backend's settings from BACKEND_* environment variables.
package config

import (
	"fmt"
	"time"

	"github.com/caarlos0/env/v11"
)

type Config struct {
	DatabaseURL string `env:"DATABASE_URL,required"`
	HTTPAddr    string `env:"HTTP_ADDR" envDefault:":8080"`
	ParserAddr  string `env:"PARSER_ADDR" envDefault:"localhost:50051"`
	// The parser needs a few seconds per statement, longer with OCR (ADR 0005).
	ParseTimeout time.Duration `env:"PARSE_TIMEOUT" envDefault:"120s"`
	// How many documents are parsed at once; keep it at or below the parser's workers.
	ParseConcurrency int    `env:"PARSE_CONCURRENCY" envDefault:"2"`
	MaxUploadMB      int    `env:"MAX_UPLOAD_MB" envDefault:"32"`
	LogFormat        string `env:"LOG_FORMAT" envDefault:"json"`
}

func Load() (Config, error) {
	cfg, err := env.ParseAsWithOptions[Config](env.Options{Prefix: "BACKEND_"})
	if err != nil {
		return Config{}, fmt.Errorf("load config: %w", err)
	}
	return cfg, nil
}

func (c Config) MaxUploadBytes() int64 {
	return int64(c.MaxUploadMB) << 20
}
