package config

import "testing"

func TestAccessNeedsBothSettingsOrNeither(t *testing.T) {
	t.Setenv("BACKEND_DATABASE_URL", "postgres://localhost/finchie")

	cases := []struct {
		domain, aud string
		enabled     bool
		fails       bool
	}{
		{"", "", false, false},
		{"https://team.cloudflareaccess.com", "aud", true, false},
		{"https://team.cloudflareaccess.com", "", false, true},
		{"", "aud", false, true},
	}
	for _, tc := range cases {
		t.Setenv("BACKEND_ACCESS_TEAM_DOMAIN", tc.domain)
		t.Setenv("BACKEND_ACCESS_AUD", tc.aud)
		cfg, err := Load()
		if (err != nil) != tc.fails {
			t.Fatalf("domain=%q aud=%q: err = %v, want failure %v", tc.domain, tc.aud, err, tc.fails)
		}
		if err == nil && cfg.AccessEnabled() != tc.enabled {
			t.Fatalf("domain=%q aud=%q: enabled = %v", tc.domain, tc.aud, cfg.AccessEnabled())
		}
	}
}
