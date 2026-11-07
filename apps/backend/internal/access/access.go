// Package access lets through only requests that came through Cloudflare Access (ADR 0008).
//
// Access signs a JWT for every request it lets through and passes it in a header. Checking it here
// means a mistake in the Cloudflare setup (a route without an Access application, say) does not
// expose the ledger: the request still arrives without a valid token and is refused.
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
			if _, err := v.verifier.Verify(request.Context(), token); err != nil {
				slog.WarnContext(request.Context(), "rejected Cloudflare Access token", "error", err)
				return c.JSON(http.StatusUnauthorized, problem{Message: "invalid Cloudflare Access token"})
			}
			return next(c)
		}
	}
}
