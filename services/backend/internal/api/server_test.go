package api

import (
	"bytes"
	"encoding/json"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/labstack/echo/v5"
	"github.com/riverqueue/river"
	"github.com/riverqueue/river/riverdriver/riverpgxv5"

	"github.com/hsin19/Finchie/services/backend/internal/testdb"
)

func newAPI(t *testing.T, maxUploadBytes int64) (*echo.Echo, *pgxpool.Pool) {
	t.Helper()
	pool := testdb.Pool(t)
	// Insert-only client: jobs are queued but nothing works them in these tests.
	jobs, err := river.NewClient(riverpgxv5.New(pool), &river.Config{})
	if err != nil {
		t.Fatal(err)
	}
	e := echo.New()
	RegisterHandlers(e, NewStrictHandler(NewServer(pool, jobs, maxUploadBytes), nil))
	return e, pool
}

func postFile(t *testing.T, e *echo.Echo, field, name string, content []byte) *httptest.ResponseRecorder {
	t.Helper()
	var body bytes.Buffer
	form := multipart.NewWriter(&body)
	part, err := form.CreateFormFile(field, name)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := part.Write(content); err != nil {
		t.Fatal(err)
	}
	if err := form.Close(); err != nil {
		t.Fatal(err)
	}
	request := httptest.NewRequestWithContext(t.Context(), http.MethodPost, "/api/documents", &body)
	request.Header.Set("Content-Type", form.FormDataContentType())
	recorder := httptest.NewRecorder()
	e.ServeHTTP(recorder, request)
	return recorder
}

func get(t *testing.T, e *echo.Echo, path string) *httptest.ResponseRecorder {
	t.Helper()
	recorder := httptest.NewRecorder()
	e.ServeHTTP(recorder, httptest.NewRequestWithContext(t.Context(), http.MethodGet, path, nil))
	return recorder
}

func decode[T any](t *testing.T, recorder *httptest.ResponseRecorder) T {
	t.Helper()
	var value T
	if err := json.Unmarshal(recorder.Body.Bytes(), &value); err != nil {
		t.Fatalf("decode %q: %v", recorder.Body.String(), err)
	}
	return value
}

func queuedJobs(t *testing.T, pool *pgxpool.Pool) int {
	t.Helper()
	var n int
	if err := pool.QueryRow(t.Context(), "SELECT count(*) FROM river_job WHERE kind = 'parse_document'").Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func TestUploadStoresTheDocumentAndQueuesOneParse(t *testing.T) {
	e, pool := newAPI(t, 1<<20)

	first := postFile(t, e, "file", "statement.eml", []byte("From: bank\r\n\r\nhello"))
	if first.Code != http.StatusCreated {
		t.Fatalf("status = %d: %s", first.Code, first.Body)
	}
	doc := decode[Document](t, first)
	if doc.Status != Pending || doc.ContentType != "message/rfc822" || doc.SizeBytes != 19 || len(doc.Sha256) != 64 {
		t.Fatalf("document = %+v", doc)
	}

	again := postFile(t, e, "file", "renamed.eml", []byte("From: bank\r\n\r\nhello"))
	if again.Code != http.StatusOK || decode[Document](t, again).Id != doc.Id {
		t.Fatalf("re-upload: %d %s", again.Code, again.Body)
	}
	if n := queuedJobs(t, pool); n != 1 {
		t.Fatalf("queued jobs = %d, want 1", n)
	}
}

func TestUploadDetectsPDFsFromTheirBytes(t *testing.T) {
	e, _ := newAPI(t, 1<<20)
	recorder := postFile(t, e, "file", "whatever.bin", []byte("%PDF-1.7 ..."))
	if got := decode[Document](t, recorder).ContentType; got != "application/pdf" {
		t.Fatalf("content type = %s", got)
	}
}

func TestUploadRejectsBadRequests(t *testing.T) {
	e, _ := newAPI(t, 16)
	cases := map[string]struct {
		field   string
		content []byte
		want    int
	}{
		"missing file field": {"attachment", []byte("x"), http.StatusBadRequest},
		"empty file":         {"file", nil, http.StatusBadRequest},
		"too large":          {"file", bytes.Repeat([]byte("x"), 17), http.StatusRequestEntityTooLarge},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			if got := postFile(t, e, tc.field, "a.eml", tc.content).Code; got != tc.want {
				t.Fatalf("status = %d, want %d", got, tc.want)
			}
		})
	}
}

func TestReadEndpoints(t *testing.T) {
	e, _ := newAPI(t, 1<<20)
	postFile(t, e, "file", "a.eml", []byte("one"))

	if docs := decode[[]Document](t, get(t, e, "/api/documents?limit=10")); len(docs) != 1 {
		t.Fatalf("documents = %+v", docs)
	}
	if statements := decode[[]Statement](t, get(t, e, "/api/statements")); len(statements) != 0 {
		t.Fatalf("statements = %+v", statements)
	}
	for _, path := range []string{"/api/documents/999", "/api/statements/999/transactions"} {
		if got := get(t, e, path).Code; got != http.StatusNotFound {
			t.Errorf("%s: status = %d", path, got)
		}
	}
}
