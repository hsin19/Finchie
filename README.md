# Finchie

Finchie = Finance + Finch

Finchie is a personal financial data integration tool that automatically collects, processes, and visualizes your financial data to help you understand spending patterns effortlessly.

> **This README describes V1, which is frozen at tag `v1.0.0`.** V2 is rebuilt in place on `main`, with V1 kept only as a reference.

## Why V2

- **Ingestion stalled on Gmail OAuth.** An OAuth app in *Testing* status gets refresh tokens that expire after 7 days, and publishing an app that requests the restricted `gmail.readonly` scope requires Google's verification (privacy policy, demo video, review). Unattended runs never became practical. The IMAP fetcher works around this, but only with an App Password that grants full mailbox access.
- **Parsers failed silently.** The Taishin parser was written against a 2025 statement. On 2026 statements, which list several Richart cards per bill, it found 1 card and 17 of 50 transactions, and still reported success. Nothing reconciled the parsed transactions against the statement total.
- **Money was stored as `float64`.**
- **The deployment target changed.** The planned Azure Functions + Cosmos DB + GitHub Pages + scheduled GitHub Actions setup is replaced by a self-hosted homelab (Postgres, Cloudflare Tunnel and Access) that already runs other services.
- **The scope grew.** Finchie becomes a personal finance platform that also takes over InTheGreenYet (investment tracking), whose Notion backend was too slow to use.
- **Fetching, parsing, and storing were one batch job.** V2 gives ingestion and state to a Go backend and turns parsing into a stateless Python service behind gRPC.

## Features

- Automatically parses financial statements from multiple sources
- Displays visual analytics for spending trends and categories
- Restricts access to personal accounts for enhanced security
- Updates automatically on a schedule, requiring no manual intervention
- Adapts to both desktop and mobile devices with responsive design

## Technical Architecture & Tech Stack

The Finchie system is organized into three interconnected services under a `services` directory, designed with a modular approach and deployed independently:

### 🛠️ [Ledger Service](services/ledger-svc/)
Serves as the central hub for financial data storage and retrieval, processing incoming REST requests from the Statement Fetcher and providing RESTful endpoints for the Web App service.

- **Go**: Efficient backend development
- **Azure Functions**: Serverless deployment on Azure
- **Azure Cosmos DB (MongoDB API)**: NoSQL database storage
- **OAuth**: Secure authentication

### 📡 [Statement Fetcher](services/statement-fetcher/)
Automatically fetches and processes statements from multiple sources, extracting structured data, and sending it to the ledger service via RESTful HTTP requests for permanent storage.

- **Python**: Data extraction and processing
- **Gmail API**: Fetching financial emails
- **GitHub Actions**: Scheduled execution via cron jobs (no standalone deployment)

### 🌍 Web App
Delivers a responsive, user-friendly interface that fetches and visualizes financial data by calling the Ledger Service's REST endpoints.

- **Next.js**: Modern frontend framework
- **React**: Dynamic UI components
- **GitHub Pages**: Static site deployment

## Service Communication

- **Statement Fetcher to Ledger Service**: Sends structured data via HTTP POST requests to API endpoints.
- **Web App to Ledger Service**: Fetches data using HTTP GET requests with OAuth authentication.

## Deployment Workflow

- **Statement Fetcher**: Triggered daily by GitHub Actions, pushes data to the Ledger Service.
- **Ledger Service**: Deployed to Azure Functions, handles data storage and retrieval.
- **Web App**: Hosted on GitHub Pages, pulls data from the Ledger Service.