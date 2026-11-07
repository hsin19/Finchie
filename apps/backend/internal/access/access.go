// Package access lets through only requests that came through Cloudflare Access (ADR 0008).
//
// Access signs a JWT for every request it lets through and passes it in a header. Checking it here
// means a mistake in the Cloudflare setup (a route without an Access application, say) does not
// expose the ledger: the request still arrives without a valid token and is refused.
//
// A token without an e-mail address belongs to a machine, an Access service token (the mailbox
// Worker, ADR 0010), not to a person signed in: it may upload a document and do nothing else.
package access

import (
	"context"
	"log/slog"
	"net/http"
	"slices"
	"strings"

	"github.com/coreos/go-oidc/v3/oidc"
	"github.com/labstack/echo/v5"
)

// Header carries the token Access signs for each request it lets through.
const Header = "Cf-Access-Jwt-Assertion"

// UploadPath is the one route a service token may call, with POST.
const UploadPath = "/api/documents"

type Verifier struct {
	verifier *oidc.IDTokenVerifier
}

// New verifies tokens that the team domain (https://<team>.cloudflareaccess.com) issued for one Access
// application, identified by its AUD tag. The signing keys come from the team's certs endpoint and are
// cached; Cloudflare rotates them.
func New(ctx context.Context, teamDomain, audience string) *Verifier {
	issuer := strings.TrimRight(teamDomain, "/")
	keys := oidc.NewRemoteKeySet(ctx, issuer+"/cdn-cgi/access/certs")
	return &Verifier{verifier: oidc.NewVerifier(issuer, keys, &oidc.Config{ClientID: audience})}
}

type problem struct {
	Message string `json:"message"`
}

// Middleware answers 401 unless the request carries a valid token. The paths in skip pass as they
// are: the health check is called from inside the network (Docker, the monitoring probe), never
// through Access.
func (v *Verifier) Middleware(skip ...string) echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c *echo.Context) error {
			request := c.Request()
			if slices.Contains(skip, request.URL.Path) {
				return next(c)
			}
			token := request.Header.Get(Header)
			if token == "" {
				return c.JSON(http.StatusUnauthorized, problem{Message: "sign in through Cloudflare Access"})
			}
			verified, err := v.verifier.Verify(request.Context(), token)
			if err != nil {
				slog.WarnContext(request.Context(), "rejected Cloudflare Access token", "error", err)
				return c.JSON(http.StatusUnauthorized, problem{Message: "invalid Cloudflare Access token"})
			}
			var claims struct {
				Email string `json:"email"`
			}
			if err := verified.Claims(&claims); err != nil || claims.Email == "" {
				if request.Method != http.MethodPost || request.URL.Path != UploadPath {
					return c.JSON(http.StatusForbidden, problem{Message: "a service token may only upload documents"})
				}
			}
			return next(c)
		}
	}
}
