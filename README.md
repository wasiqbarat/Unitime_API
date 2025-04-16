# Unitime Solver API wrapper

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-311/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.0-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/docker-compatible-brightgreen.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A REST API service that wraps the [CPSolver](https://github.com/UniTime/cpsolver) library for university timetabling and scheduling problems.

## 📋 Table of Contents
- [Features](#-features)
- [Requirements](#-requirements)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
  - [Local Installation](#local-installation)
  - [Docker Installation](#docker-installation)
  - [Key Endpoints](#key-endpoints)
- [Docker Deployment](#-docker-deployment)
  - [Volume Management](#volume-management)
- [Contributing](#-contributing)
- [License](#-license)
- [Acknowledgments](#acknowledgments)

## ✨ Features

- **RESTful API Interface**: Modern REST endpoints for all timetabling operations
- **Multiple Input Formats**: Support for both JSON and XML input formats
- **Asynchronous Processing**: Non-blocking solution computation
- **Real-time Status Updates**: Track solver progress in real-time
- **Persistence**: Solution storage and retrieval capabilities
- **Docker Support**: Containerized deployment ready
- **Comprehensive Documentation**: Auto-generated API documentation

## 🔧 Requirements

- Python 3.11+
- Java Runtime Environment (JRE) 17+
- Docker (optional, for containerized deployment)
- CPSolver library

## 🚀 Quick Start

The fastest way to get started is using Docker:

```bash
# Clone the repository
git clone https://github.com/yourusername/unitime-api.git
cd unitime-api

# Start the service
docker-compose up -d

# The API will be available at http://localhost:8000
# API documentation at http://localhost:8000/docs
```

## 📥 Installation

### Local Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/unitime-api.git
cd unitime-api
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up CPSolver:
```bash
python setup_cpsolver.py
```

### Docker Installation

Build and run using Docker:

```bash
# Build the image
docker build -t unitime-solver-api .

# Run the container
docker run -p 8000:8000 -v /path/to/cpsolver:/app/cpsolver unitime-solver-api
```

### Key Endpoints

#### Health Check
```http
GET /
```

#### Solver Control
```http
POST /solver/start
GET /solver/status
POST /solver/stop
```

#### Problem Management
```http
POST /problems          # Submit problem (JSON)
POST /problems/xml      # Submit problem (XML)
GET /problems/{id}      # Get status
DELETE /problems/{id}   # Cancel solver
```

#### Solution Retrieval
```http
GET /problems/{id}/solution      # Get JSON solution
GET /problems/{id}/solution/xml  # Get XML solution
```

## 🐳 Docker Deployment

The project includes both Dockerfile and docker-compose.yml for easy deployment:

```bash
# Using docker-compose (recommended)
docker-compose up -d

# Scale if needed
docker-compose up -d --scale api=3
```

### Volume Management
- CPSolver data is persisted using named volumes
- Configuration can be mounted using Docker volumes
- Logs are available through Docker logging

## 👥 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License

## Acknowledgments

- [CPSolver](https://github.com/UniTime/cpsolver) - The core timetabling solver
- [FastAPI](https://fastapi.tiangolo.com/) - The web framework used
