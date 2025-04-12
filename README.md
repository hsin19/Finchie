# Finchie

Finchie = Finance + Finch

Finchie is a personal financial data integration tool that automatically collects, processes, and visualizes your financial data to help you understand spending patterns effortlessly.

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