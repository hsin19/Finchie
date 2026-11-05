# Statement Fetcher

## Install

- Install [uv](https://docs.astral.sh/uv/getting-started/installation/) for managing Python dependencies
- Run `uv sync --directory services/statement-fetcher --dev` to install dependencies

## Fetching mail

Two interchangeable fetchers ship with the service. Pick **one** in `config.json` and
set the other's `disable: true`.

| Fetcher | Auth | Token lifetime | Verification | Best for |
|---|---|---|---|---|
| `gmail` (OAuth) | Google OAuth 2.0 | Testing app: **7 days**; Production: until revoked | Restricted scope → privacy policy URL, demo video, multi-round review | Workspace apps that need to read other users' mail |
| `imap` (App Password) | Gmail App Password | **Never expires** (until revoked) | None | Reading your own mailbox on a long-running schedule |

For unattended automation (e.g. GitHub Actions cron), the IMAP path is usually less
painful — Google's restricted-scope verification flow is disproportionate for a
single-user side project.

### Option A — IMAP + Gmail App Password (recommended)

1. Enable **2-Step Verification** on the Google account: <https://myaccount.google.com/signinoptions/twosv>
2. Generate an App Password: <https://myaccount.google.com/apppasswords> → "Mail" / "Other" → copy the 16-character string
3. Edit `config/config.json` → set `fetcher.imap.disable: false`, fill in `user`, and disable `fetcher.gmail` if you no longer need it
4. Export the password as an environment variable (the fetcher reads `IMAP_PASSWORD` by default):
   ```sh
   export IMAP_PASSWORD='xxxx xxxx xxxx xxxx'
   ```

`config.json` example:
```json
"imap": {
    "host": "imap.gmail.com",
    "port": 993,
    "user": "you@gmail.com",
    "password_env_var": "IMAP_PASSWORD",
    "mailbox": "INBOX",
    "query": "label:bill",
    "days_ago": 30,
    "use_gmail_search": true,
    "disable": false
}
```

Notes:
- `use_gmail_search: true` sends the query via Gmail's `X-GM-RAW` IMAP extension, so you can keep using Gmail search syntax (`label:`, `has:attachment`, `from:`, …).
- For a non-Gmail IMAP server, set `use_gmail_search: false` and supply standard IMAP search criteria as `query` (e.g. `FROM "bank.com"`).
- The fetcher only does `SELECT … readonly`; it cannot modify your mailbox.

For **GitHub Actions** automation, add the App Password as a repository secret
(`Settings → Secrets and variables → Actions`, name it `IMAP_PASSWORD`) and expose
it to the workflow via `env: IMAP_PASSWORD: ${{ secrets.IMAP_PASSWORD }}`.

### Option B — Gmail API + OAuth

#### Google Cloud Setup
1. Create a new project (or use an existing one) in the [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to "Enabled APIs & Services" => search for "Gmail API" => click "Enable"
3. OAuth configuration:
    1. Create OAuth consent screen
    2. Set Audience => "External" => Add test users (add your email)
    3. Create credentials => Create OAuth client ID => Desktop app => Download JSON file
    4. Configure OAuth consent screen => Add scope => `.../auth/gmail.readonly`

#### Local Setup and Authentication
1. Rename the downloaded JSON file to `credentials.json` and place it in `services/statement-fetcher/config/secret/gmail/credentials.json`
2. First-time setup will open a browser window to authorize your application
3. After authorization, a `token.json` file will be created at `services/statement-fetcher/config/secret/gmail/token.json` for subsequent authentication

> **Heads-up:** Refresh tokens issued by an OAuth app in **Testing** status expire after 7 days. Moving the app to Production requires Google's verification flow (privacy policy URL, demo video, …) for restricted scopes like `gmail.readonly`. For solo / personal use, Option A is usually the lower-friction choice.

## Deploy

### GitHub Actions

This project uses GitHub Actions for automated deployment. You need to run it locally once to get the refresh token and set it up in GitHub Actions secrets.

1. Run the Gmail extractor locally once to generate `token.json`
2. Copy the `refresh_token` value from `token.json`
3. Set up in GitHub repository:
   - Go to Settings => Secrets and variables => Actions
   - Add repository secret:
     - Name: `EXTRACT_GMAIL_REFRESH_TOKEN`
     - Value: Paste the refresh token value copied earlier

This allows GitHub Actions to use the refresh token to automatically obtain new access tokens without manual authentication.

### Resources
- [uv CLI](https://docs.astral.sh/uv/reference/cli/)
- [Gmail API Documentation](https://developers.google.com/gmail/api/guides)
