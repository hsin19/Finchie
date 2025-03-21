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

### 📡 Data Pipeline
Executes an automated ETL process to extract financial data from multiple sources, transform it into structured data, and load it into the API via RESTful HTTP requests for permanent storage.

- **Python**: Data extraction and processing  
- **Gmail API**: Fetching financial emails  
- **GitHub Actions**: Scheduled execution via cron jobs (no standalone deployment)  

### 🛠️ API
Serves as the central hub for data storage and retrieval, processing incoming REST requests from the Data Pipeline and providing RESTful endpoints for the Web service.

- **Go**: Efficient backend development  
- **Azure Functions**: Serverless deployment on Azure  
- **Azure Cosmos DB**: NoSQL database storage  
- **OAuth**: Secure authentication  

### 🌍 Web
Delivers a responsive, user-friendly interface that fetches and visualizes financial data by calling the API’s REST endpoints.

- **Next.js**: Modern frontend framework  
- **React**: Dynamic UI components  
- **GitHub Pages**: Static site deployment  

## Service Communication

- **Data Pipeline to API**: Sends structured data via HTTP POST requests to Azure Functions endpoints.  
- **Web to API**: Fetches data using HTTP GET requests with OAuth authentication.  

## Deployment Workflow

- **Data Pipeline**: Triggered daily by GitHub Actions, pushes data to the API.  
- **API**: Deployed to Azure Functions, handles data storage and retrieval.  
- **Web**: Hosted on GitHub Pages, pulls data from the API.  