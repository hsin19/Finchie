package api

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"html"
	"mime"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"github.com/hsin19/finchie/apps/backend/internal/db/dbq"
	parserv1 "github.com/hsin19/finchie/apps/backend/internal/gen/finchie/parser/v1"
)

// openTimeout bounds a call that reads an e-mail and decrypts its PDFs: no OCR, unlike a parse.
const openTimeout = 30 * time.Second

// bodyPolicy sandboxes the e-mail body even when its URL is opened on its own: no scripts, forms,
// or plugins, an origin of its own, and only images from elsewhere, as a mail client shows them.
// Some banks still link images over http; they load upgraded to https. Links may open a new tab,
// outside the sandbox, so the bank's site works there.
const bodyPolicy = "sandbox allow-popups allow-popups-to-escape-sandbox; default-src 'none'; " +
	"img-src data: https:; style-src 'unsafe-inline'; frame-ancestors 'self'; upgrade-insecure-requests"

var doctype = regexp.MustCompile(`(?is)^\s*<!doctype[^>]*>`)

// openFailure is why a document could not be opened, as an HTTP status and a message.
type openFailure struct {
	status  int
	problem ProblemJSONResponse
}

// open has the parser open the stored original; nothing it returns is stored (ADR 0012).
func (s *Server) open(ctx context.Context, id int64) (*parserv1.OpenDocumentResponse, *openFailure, error) {
	row, err := dbq.New(s.pool).GetDocumentContent(ctx, id)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, &openFailure{http.StatusNotFound, notFound("document", id)}, nil
	}
	if err != nil {
		return nil, nil, fmt.Errorf("get document %d content: %w", id, err)
	}
	ctx, cancel := context.WithTimeout(ctx, openTimeout)
	defer cancel()
	opened, err := s.parser.OpenDocument(ctx, &parserv1.OpenDocumentRequest{
		DocumentId:  strconv.FormatInt(id, 10),
		Filename:    row.Filename,
		ContentType: row.ContentType,
		Content:     row.Content,
	})
	switch status.Code(err) {
	case codes.OK:
		return opened, nil, nil
	case codes.InvalidArgument, codes.Unimplemented:
		message := "the parser cannot open this document: " + status.Convert(err).Message()
		return nil, &openFailure{http.StatusUnprocessableEntity, ProblemJSONResponse{Message: message}}, nil
	case codes.Unavailable, codes.DeadlineExceeded:
		return nil, &openFailure{http.StatusServiceUnavailable, ProblemJSONResponse{Message: "the parser is not reachable; try again"}}, nil
	default:
		return nil, nil, fmt.Errorf("open document %d: %w", id, err)
	}
}

func (s *Server) GetDocumentPreview(ctx context.Context, request GetDocumentPreviewRequestObject) (GetDocumentPreviewResponseObject, error) {
	opened, failure, err := s.open(ctx, request.Id)
	switch {
	case err != nil:
		return nil, err
	case failure == nil:
	case failure.status == http.StatusNotFound:
		return GetDocumentPreview404JSONResponse{failure.problem}, nil
	case failure.status == http.StatusUnprocessableEntity:
		return GetDocumentPreview422JSONResponse(failure.problem), nil
	default:
		return GetDocumentPreview503JSONResponse(failure.problem), nil
	}

	preview := DocumentPreview{Files: make([]PreviewFile, len(opened.GetFiles()))}
	for i, file := range opened.GetFiles() {
		preview.Files[i] = PreviewFile{
			Index:       i,
			Filename:    file.GetFilename(),
			ContentType: file.GetContentType(),
			SizeBytes:   len(file.GetContent()),
			Locked:      file.GetLocked(),
			Primary:     file.GetPrimary(),
		}
	}
	if email := opened.GetEmail(); email != nil {
		preview.Email = &EmailPreview{
			Sender:    email.GetSender(),
			Recipient: email.GetRecipient(),
			Subject:   email.GetSubject(),
			HasBody:   email.GetHtml() != "" || email.GetText() != "",
		}
		if email.GetDate() != nil {
			date := email.GetDate().AsTime()
			preview.Email.Date = &date
		}
	}
	return GetDocumentPreview200JSONResponse(preview), nil
}

func (s *Server) GetDocumentPreviewPdf(ctx context.Context, request GetDocumentPreviewPdfRequestObject) (GetDocumentPreviewPdfResponseObject, error) {
	opened, failure, err := s.open(ctx, request.Id)
	switch {
	case err != nil:
		return nil, err
	case failure == nil:
	case failure.status == http.StatusNotFound:
		return GetDocumentPreviewPdf404JSONResponse{failure.problem}, nil
	case failure.status == http.StatusUnprocessableEntity:
		return GetDocumentPreviewPdf422JSONResponse(failure.problem), nil
	default:
		return GetDocumentPreviewPdf503JSONResponse(failure.problem), nil
	}

	for _, file := range opened.GetFiles() {
		if !file.GetPrimary() {
			continue
		}
		disposition := mime.FormatMediaType("inline", map[string]string{"filename": file.GetFilename()})
		nosniff := "nosniff"
		return GetDocumentPreviewPdf200ApplicationpdfResponse{
			Body:          bytes.NewReader(file.GetContent()),
			ContentLength: int64(len(file.GetContent())),
			Headers: GetDocumentPreviewPdf200ResponseHeaders{
				ContentDisposition:  &disposition,
				XContentTypeOptions: &nosniff,
			},
		}, nil
	}
	return GetDocumentPreviewPdf404JSONResponse{ProblemJSONResponse{Message: fmt.Sprintf("document %d holds no PDF", request.Id)}}, nil
}

func (s *Server) GetDocumentPreviewBody(ctx context.Context, request GetDocumentPreviewBodyRequestObject) (GetDocumentPreviewBodyResponseObject, error) {
	opened, failure, err := s.open(ctx, request.Id)
	switch {
	case err != nil:
		return nil, err
	case failure == nil:
	case failure.status == http.StatusNotFound:
		return GetDocumentPreviewBody404JSONResponse{failure.problem}, nil
	case failure.status == http.StatusUnprocessableEntity:
		return GetDocumentPreviewBody422JSONResponse(failure.problem), nil
	default:
		return GetDocumentPreviewBody503JSONResponse(failure.problem), nil
	}

	email := opened.GetEmail()
	if email.GetHtml() == "" && email.GetText() == "" {
		return GetDocumentPreviewBody404JSONResponse{ProblemJSONResponse{Message: fmt.Sprintf("document %d has no e-mail body", request.Id)}}, nil
	}
	page := bodyPage(email.GetHtml(), email.GetText())
	policy, referrer, nosniff := bodyPolicy, "no-referrer", "nosniff"
	return GetDocumentPreviewBody200TexthtmlCharsetUtf8Response{
		Body:          strings.NewReader(page),
		ContentLength: int64(len(page)),
		Headers: GetDocumentPreviewBody200ResponseHeaders{
			ContentSecurityPolicy: &policy,
			ReferrerPolicy:        &referrer,
			XContentTypeOptions:   &nosniff,
		},
	}, nil
}

// bodyPage makes the body a page whose links open in a new tab: a sandboxed frame cannot show the
// bank's site in place. The base element goes after any doctype, which must stay first.
func bodyPage(htmlBody, text string) string {
	const base = `<base target="_blank">`
	if htmlBody == "" {
		return `<!doctype html><meta charset="utf-8">` + base +
			`<pre style="white-space: pre-wrap; font: 14px/1.6 system-ui, sans-serif; margin: 16px">` +
			html.EscapeString(text) + `</pre>`
	}
	at := 0
	if loc := doctype.FindStringIndex(htmlBody); loc != nil {
		at = loc[1]
	}
	return htmlBody[:at] + base + htmlBody[at:]
}

func (s *Server) GetDocumentPreviewFile(ctx context.Context, request GetDocumentPreviewFileRequestObject) (GetDocumentPreviewFileResponseObject, error) {
	opened, failure, err := s.open(ctx, request.Id)
	switch {
	case err != nil:
		return nil, err
	case failure == nil:
	case failure.status == http.StatusNotFound:
		return GetDocumentPreviewFile404JSONResponse{failure.problem}, nil
	case failure.status == http.StatusUnprocessableEntity:
		return GetDocumentPreviewFile422JSONResponse(failure.problem), nil
	default:
		return GetDocumentPreviewFile503JSONResponse(failure.problem), nil
	}

	files := opened.GetFiles()
	if request.Index < 0 || request.Index >= len(files) {
		return GetDocumentPreviewFile404JSONResponse{ProblemJSONResponse{Message: fmt.Sprintf("document %d has no file %d", request.Id, request.Index)}}, nil
	}
	file := files[request.Index]
	// The same rule as the original (GetDocumentContent): only a PDF opens in place.
	contentType, disposition := "application/octet-stream", "attachment"
	if file.GetContentType() == contentTypePDF {
		contentType, disposition = contentTypePDF, "inline"
	}
	disposition = mime.FormatMediaType(disposition, map[string]string{"filename": file.GetFilename()})
	nosniff := "nosniff"
	return GetDocumentPreviewFile200AsteriskResponse{
		Body:          bytes.NewReader(file.GetContent()),
		ContentType:   contentType,
		ContentLength: int64(len(file.GetContent())),
		Headers: GetDocumentPreviewFile200ResponseHeaders{
			ContentDisposition:  &disposition,
			XContentTypeOptions: &nosniff,
		},
	}, nil
}
