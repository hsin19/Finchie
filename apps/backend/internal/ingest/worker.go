// Package ingest parses stored documents in background jobs and stores the results (ADR 0005).
package ingest

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/riverqueue/river"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"github.com/hsin19/finchie/apps/backend/internal/db/dbq"
	parserv1 "github.com/hsin19/finchie/apps/backend/internal/gen/finchie/parser/v1"
)

// ParseDocumentArgs is the job enqueued on upload and on re-parse.
type ParseDocumentArgs struct {
	DocumentID int64 `json:"document_id"`
}

func (ParseDocumentArgs) Kind() string { return "parse_document" }

func (ParseDocumentArgs) InsertOpts() river.InsertOpts {
	// Retries only happen while the parser is unreachable; a few minutes of back-off covers a restart.
	return river.InsertOpts{MaxAttempts: 6}
}

type Worker struct {
	river.WorkerDefaults[ParseDocumentArgs]
	pool    *pgxpool.Pool
	parser  parserv1.ParserServiceClient
	timeout time.Duration
}

func NewWorker(pool *pgxpool.Pool, parser parserv1.ParserServiceClient, timeout time.Duration) *Worker {
	return &Worker{pool: pool, parser: parser, timeout: timeout}
}

// Timeout leaves room to store the result after the parser's own deadline.
func (w *Worker) Timeout(*river.Job[ParseDocumentArgs]) time.Duration {
	return w.timeout + 30*time.Second
}

func (w *Worker) Work(ctx context.Context, job *river.Job[ParseDocumentArgs]) error {
	id := job.Args.DocumentID
	queries := dbq.New(w.pool)
	doc, err := queries.GetDocumentContent(ctx, id)
	if errors.Is(err, pgx.ErrNoRows) {
		return river.JobCancel(fmt.Errorf("document %d no longer exists", id))
	}
	if err != nil {
		return fmt.Errorf("load document %d: %w", id, err)
	}

	callCtx, cancel := context.WithTimeout(ctx, w.timeout)
	response, err := w.parser.ParseDocument(callCtx, &parserv1.ParseDocumentRequest{
		DocumentId:  strconv.FormatInt(id, 10),
		Filename:    doc.Filename,
		ContentType: doc.ContentType,
		Content:     doc.Content,
	})
	cancel()

	if err != nil {
		if retryable(err) && job.Attempt < job.MaxAttempts {
			return fmt.Errorf("parse document %d: %w", id, err)
		}
		return w.fail(ctx, id, describe(err))
	}

	outcome, err := Store(ctx, w.pool, id, response)
	if errors.Is(err, ErrInvalidResponse) {
		return w.fail(ctx, id, err.Error())
	}
	if err != nil {
		return fmt.Errorf("store document %d: %w", id, err)
	}
	slog.InfoContext(ctx, "document parsed", "document_id", id, "status", outcome,
		"parser", response.GetParser(), "transactions", len(response.GetStatement().GetTransactions()))
	return nil
}

// fail records why a document cannot be parsed and stops River from retrying it.
func (w *Worker) fail(ctx context.Context, id int64, reason string) error {
	err := dbq.New(w.pool).FinishDocument(ctx, dbq.FinishDocumentParams{
		ID:       id,
		Status:   StatusFailed,
		Error:    &reason,
		Warnings: []string{},
	})
	if err != nil {
		return fmt.Errorf("mark document %d failed: %w", id, err)
	}
	slog.WarnContext(ctx, "document failed", "document_id", id, "reason", reason)
	return river.JobCancel(errors.New(reason))
}

// retryable reports whether the parser might succeed later (ADR 0005). Everything else is permanent:
// the document, its password, or the parser has to change first.
func retryable(err error) bool {
	switch status.Code(err) {
	case codes.Unavailable, codes.DeadlineExceeded, codes.ResourceExhausted:
		return true
	default:
		return false
	}
}

func describe(err error) string {
	s := status.Convert(err)
	return fmt.Sprintf("%s: %s", s.Code(), s.Message())
}
