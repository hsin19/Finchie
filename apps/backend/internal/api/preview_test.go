package api

import (
	"context"
	"fmt"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/labstack/echo/v5"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/timestamppb"

	parserv1 "github.com/hsin19/finchie/apps/backend/internal/gen/finchie/parser/v1"
)

// openingParser answers OpenDocument; the API never calls the embedded (nil) ParseDocument.
type openingParser struct {
	parserv1.ParserServiceClient
	response *parserv1.OpenDocumentResponse
	err      error
	requests []*parserv1.OpenDocumentRequest
}

func (p *openingParser) OpenDocument(_ context.Context, in *parserv1.OpenDocumentRequest, _ ...grpc.CallOption) (*parserv1.OpenDocumentResponse, error) {
	p.requests = append(p.requests, in)
	return p.response, p.err
}

const storedEmail = "From: bank\r\n\r\nhello"

// previewAPI stores one e-mail and answers previews of it with parser.
func previewAPI(t *testing.T, parser *openingParser) (*echo.Echo, int64) {
	t.Helper()
	e, _ := newAPIWithParser(t, 1<<20, parser)
	doc := decode[Document](t, postFile(t, e, "file", "statement.eml", []byte(storedEmail)))
	return e, doc.Id
}

func statementEmail(html, text string) *parserv1.OpenDocumentResponse {
	return &parserv1.OpenDocumentResponse{
		Email: &parserv1.Email{
			Sender:    "範例銀行 <statements@bank.example>",
			Recipient: "someone@example.com",
			Subject:   "信用卡電子帳單",
			Date:      timestamppb.New(time.Date(2026, 11, 6, 1, 30, 0, 0, time.UTC)),
			Html:      html,
			Text:      text,
		},
		Files: []*parserv1.File{
			{Filename: "帳單.pdf", ContentType: "application/pdf", Content: []byte("%PDF decrypted"), Primary: true},
			{Filename: "slip.html", ContentType: "text/html", Content: []byte("<script>alert(1)</script>")},
		},
	}
}

func TestPreviewShowsTheEmailAndItsFilesFromTheStoredOriginal(t *testing.T) {
	parser := &openingParser{response: statementEmail("<p>本期帳單</p>", "")}
	e, id := previewAPI(t, parser)

	recorder := get(t, e, fmt.Sprintf("/api/documents/%d/preview", id))
	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d: %s", recorder.Code, recorder.Body)
	}
	preview := decode[DocumentPreview](t, recorder)
	email := preview.Email
	if email == nil || email.Sender != "範例銀行 <statements@bank.example>" || email.Subject != "信用卡電子帳單" ||
		!email.HasBody || email.Date == nil || !email.Date.Equal(time.Date(2026, 11, 6, 1, 30, 0, 0, time.UTC)) {
		t.Fatalf("email = %+v", email)
	}
	want := []PreviewFile{
		{Index: 0, Filename: "帳單.pdf", ContentType: "application/pdf", SizeBytes: 14, Primary: true},
		{Index: 1, Filename: "slip.html", ContentType: "text/html", SizeBytes: 25},
	}
	if fmt.Sprint(preview.Files) != fmt.Sprint(want) {
		t.Fatalf("files = %+v, want %+v", preview.Files, want)
	}

	sent := parser.requests[0]
	if sent.GetDocumentId() != fmt.Sprint(id) || sent.GetFilename() != "statement.eml" ||
		sent.GetContentType() != "message/rfc822" || string(sent.GetContent()) != storedEmail {
		t.Fatalf("parser got %+v", sent)
	}
}

func TestPreviewFilesOpenOnlyPDFsInPlace(t *testing.T) {
	e, id := previewAPI(t, &openingParser{response: statementEmail("", "")})
	cases := []struct {
		index                    int
		code                     int
		contentType, disposition string
	}{
		{0, http.StatusOK, "application/pdf", "inline; filename*=utf-8''%E5%B8%B3%E5%96%AE.pdf"},
		// Whatever the e-mail declares, nothing but a PDF is shown on the app's origin.
		{1, http.StatusOK, "application/octet-stream", "attachment; filename=slip.html"},
		{2, http.StatusNotFound, "application/json", ""},
	}
	for _, tc := range cases {
		recorder := get(t, e, fmt.Sprintf("/api/documents/%d/preview/files/%d", id, tc.index))
		header := recorder.Header()
		if recorder.Code != tc.code || header.Get("Content-Type") != tc.contentType || header.Get("Content-Disposition") != tc.disposition {
			t.Fatalf("file %d: %d %v", tc.index, recorder.Code, header)
		}
		if tc.code == http.StatusOK && header.Get("X-Content-Type-Options") != "nosniff" {
			t.Fatalf("file %d: no nosniff", tc.index)
		}
	}
	if body := get(t, e, fmt.Sprintf("/api/documents/%d/preview/files/0", id)).Body.String(); body != "%PDF decrypted" {
		t.Fatalf("pdf = %q", body)
	}
}

func TestPreviewPDFIsTheStatementOpenedInPlace(t *testing.T) {
	e, id := previewAPI(t, &openingParser{response: statementEmail("", "")})
	recorder := get(t, e, fmt.Sprintf("/api/documents/%d/preview/pdf", id))
	header := recorder.Header()
	if recorder.Code != http.StatusOK || header.Get("Content-Type") != "application/pdf" ||
		header.Get("Content-Disposition") != "inline; filename*=utf-8''%E5%B8%B3%E5%96%AE.pdf" ||
		header.Get("X-Content-Type-Options") != "nosniff" || recorder.Body.String() != "%PDF decrypted" {
		t.Fatalf("pdf: %d %v %q", recorder.Code, header, recorder.Body)
	}

	noPDF := &parserv1.OpenDocumentResponse{Email: &parserv1.Email{Text: "hello"}}
	e, id = previewAPI(t, &openingParser{response: noPDF})
	if recorder := get(t, e, fmt.Sprintf("/api/documents/%d/preview/pdf", id)); recorder.Code != http.StatusNotFound {
		t.Fatalf("no pdf: status = %d", recorder.Code)
	}
}

func TestPreviewBodyIsASandboxedPageWhoseLinksOpenANewTab(t *testing.T) {
	cases := []struct {
		name, html, text string
		want             string
	}{
		{"html with doctype", "<!DOCTYPE html>\n<html><p>本期帳單</p></html>", "", `<!DOCTYPE html><base target="_blank">` + "\n<html><p>本期帳單</p></html>"},
		{"html fragment", "<p>本期帳單</p>", "", `<base target="_blank"><p>本期帳單</p>`},
		{"plain text", "", "a < b", "a &lt; b</pre>"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			e, id := previewAPI(t, &openingParser{response: statementEmail(tc.html, tc.text)})
			recorder := get(t, e, fmt.Sprintf("/api/documents/%d/preview/body", id))
			header := recorder.Header()
			if recorder.Code != http.StatusOK || header.Get("Content-Type") != "text/html; charset=utf-8" ||
				!strings.HasPrefix(header.Get("Content-Security-Policy"), "sandbox ") ||
				!strings.Contains(header.Get("Content-Security-Policy"), "default-src 'none'") ||
				header.Get("Referrer-Policy") != "no-referrer" || header.Get("X-Content-Type-Options") != "nosniff" {
				t.Fatalf("body: %d %v", recorder.Code, header)
			}
			if !strings.HasSuffix(recorder.Body.String(), tc.want) {
				t.Fatalf("body = %q, want it to end with %q", recorder.Body, tc.want)
			}
		})
	}
}

func TestPreviewBodyOfABarePDFIsNotFound(t *testing.T) {
	bare := &parserv1.OpenDocumentResponse{Files: []*parserv1.File{{Filename: "a.pdf", ContentType: "application/pdf"}}}
	e, id := previewAPI(t, &openingParser{response: bare})
	if recorder := get(t, e, fmt.Sprintf("/api/documents/%d/preview/body", id)); recorder.Code != http.StatusNotFound {
		t.Fatalf("status = %d", recorder.Code)
	}
	if preview := decode[DocumentPreview](t, get(t, e, fmt.Sprintf("/api/documents/%d/preview", id))); preview.Email != nil {
		t.Fatalf("email = %+v", preview.Email)
	}
}

func TestPreviewReportsWhatStoppedIt(t *testing.T) {
	cases := []struct {
		name string
		err  error
		code int
	}{
		{"unreadable", status.Error(codes.InvalidArgument, "unreadable"), http.StatusUnprocessableEntity},
		{"parser down", status.Error(codes.Unavailable, "connection refused"), http.StatusServiceUnavailable},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			e, id := previewAPI(t, &openingParser{err: tc.err})
			for _, path := range []string{"preview", "preview/pdf", "preview/body", "preview/files/0"} {
				if recorder := get(t, e, fmt.Sprintf("/api/documents/%d/%s", id, path)); recorder.Code != tc.code {
					t.Fatalf("%s: status = %d, want %d", path, recorder.Code, tc.code)
				}
			}
		})
	}

	parser := &openingParser{}
	e, _ := previewAPI(t, parser)
	if recorder := get(t, e, "/api/documents/999/preview"); recorder.Code != http.StatusNotFound || len(parser.requests) != 0 {
		t.Fatalf("unknown document: %d, parser called %d times", recorder.Code, len(parser.requests))
	}
}
