# Data Pipeline

## Install

- Install [uv](https://docs.astral.sh/uv/getting-started/installation/) for managing Python dependencies
- Run `uv sync --project services/data-pipeline` to install dependencies

## Gmail API

### Google Cloud Setup
1. Create a new project (or use an existing one) in the [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to "Enabled APIs & Services" => search for "Gmail API" => click "Enable"
3. OAuth configuration:
    1. Create OAuth consent screen
    2. Set Audience => "External" => Add test users (add your email)
    3. Create credentials => Create OAuth client ID => Desktop app => Download JSON file
    4. Configure OAuth consent screen => Add scope => `.../auth/gmail.readonly`

### Local Setup and Authentication
1. Rename the downloaded JSON file to `credentials.json` and place it in `services/data-pipeline/config/secret/gmail/credentials.json`
2. First-time setup will open a browser window to authorize your application
3. After authorization, a `token.json` file will be created at `services/data-pipeline/config/secret/gmail/token.json` for subsequent authentication

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
