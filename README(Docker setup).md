# FlexRoute

FlexRoute is an AI-powered fitness coach and workout routine builder.

It uses:

- **Electron + React (Vite)** for the desktop app
- **FastAPI + LangGraph** for the backend
- **Ollama + Mistral** for local AI
- **nomic-embed-text** for embeddings
- **Qdrant** for local RAG/vector search
- **SQLite** for application state and athlete profiles
- **Google Gemini 2.5 Flash** as a cloud AI provider
- **Docker Compose** to run the backend services

---

## Requirements

Before running FlexRoute on a new Windows laptop, install:

1. **Docker Desktop**
2. FlexRoute project folder
3. FlexRoute desktop installer

You do **not** need to separately install:

- Python
- FastAPI
- Qdrant
- Ollama
- Mistral
- nomic-embed-text
- Node.js for normal use

Docker handles the backend dependencies.

> **Disk space:** Docker images and AI models can use several GB of storage. Make sure the drive used by Docker has plenty of free space. If your C: drive is small, move Docker Desktop's disk image location to another drive before running the setup.

---

# First-Time Setup

## 1. Install Docker Desktop

Install Docker Desktop and make sure it is running.

You can verify Docker from PowerShell:

```powershell
docker info
```

If Docker responds with Client and Server information, it is ready.

---

## 2. Copy the FlexRoute Project

Copy the complete FlexRoute project folder onto the laptop.

Example:

```text
D:\My projects\Flex Route
```

The project root should contain files such as:

```text
docker-compose.yml
Dockerfile
requirements.txt
server.py
setup.bat
start_flexroute.bat
checkpoints.sqlite
.env
src\
knowledge\
flex-web\
```

---

## 3. Add the `.env` File

Place the required `.env` file in the project root.

Example:

```text
Flex Route\
├── .env
├── docker-compose.yml
├── server.py
└── ...
```

The `.env` file contains required runtime configuration such as Gemini API keys.

Do not upload or publicly share this file.

---

## 4. Run `setup.bat`

Double-click:

```text
setup.bat
```

The setup script will:

1. Build/start the Docker services
2. Download the Mistral model
3. Download the nomic-embed-text model
4. Prepare the Qdrant knowledge base

The first setup can take a while because the AI models and Docker images must be downloaded.

Mistral alone is approximately **4.4 GB**.

---

## 5. Install the FlexRoute Desktop App

Run the generated installer:

```text
FlexRoute Setup 0.0.0.exe
```

Follow the installer normally.

The application is usually installed at:

```text
%LOCALAPPDATA%\Programs\FlexRoute\FlexRoute.exe
```

---

# Normal Startup

After the first-time setup, you do not need to manually start Python, Ollama, Qdrant, or FastAPI.

Simply double-click:

```text
start_flexroute.bat
```

The launcher will:

```text
Start Docker services
        ↓
FastAPI + Qdrant + Ollama
        ↓
Open FlexRoute.exe
```

Then use FlexRoute normally.

---

# Docker Architecture

FlexRoute runs like this:

```text
FlexRoute Desktop App
        |
        v
localhost:8000
        |
        v
FastAPI Backend
   |          |
   |          |
   v          v
Ollama      Qdrant
   |
   +-- Mistral
   |
   +-- nomic-embed-text
```

The Docker Compose stack contains:

```text
flexroute-api       FastAPI + LangGraph backend
flexroute-qdrant    Vector database / RAG
flexroute-ollama    Local AI model server
```

---

# Checking Whether FlexRoute Services Are Running

Open PowerShell in the project root and run:

```powershell
docker compose ps
```

You should see:

```text
flexroute-api
flexroute-qdrant
flexroute-ollama
```

with a status similar to:

```text
Up
```

---

# Starting Services Manually

If required:

```powershell
docker compose up -d
```

`-d` means Docker runs the services in the background.

---

# Stopping FlexRoute Docker Services

To stop and remove the running containers:

```powershell
docker compose down
```

Your persistent Qdrant/Ollama data remains stored in Docker volumes.

Do **not** normally use:

```powershell
docker compose down -v
```

because `-v` deletes the Docker volumes as well.

---

# Viewing Backend Logs

If the app is not responding:

```powershell
docker compose logs -f backend
```

Press:

```text
Ctrl + C
```

to exit the log view.

---

# Checking Ollama Models

Run:

```powershell
docker compose exec ollama ollama list
```

You should see:

```text
mistral:latest
nomic-embed-text:latest
```

If a model is missing:

```powershell
docker compose exec ollama ollama pull mistral
docker compose exec ollama ollama pull nomic-embed-text
```

---

# Rebuilding the Qdrant Knowledge Base

If the RAG collection is missing or needs to be recreated:

```powershell
docker compose exec backend python src/document_loader.py
```

This rebuilds the `exercise_cues` collection from the project's knowledge documents.

---

# Persistent Data

FlexRoute keeps important data across container recreations.

### Qdrant

Stored in the Docker volume:

```text
qdrant_data
```

### Ollama models

Stored in:

```text
ollama_data
```

### SQLite

The backend uses:

```text
checkpoints.sqlite
```

The project file is mounted into the backend container so application state remains available even when the backend container is recreated.

---

# Important Notes

### Docker Desktop must be running

FlexRoute's backend services depend on Docker Desktop.

If `start_flexroute.bat` reports that Docker services cannot start, open Docker Desktop first and wait until Docker is ready.

### Windows Ollama is not required

Do not manually run:

```text
ollama serve
```

FlexRoute uses the Ollama Docker container instead.

### Python virtual environment is not required for normal use

The backend Python environment exists inside the Docker image.

### Node/npm is not required for normal use

Node and npm are only required when developing or rebuilding the Electron frontend.

---

# Development

To run the Electron app in development mode:

```powershell
cd flex-web
npm install
npm run electron:dev
```

To create a new Windows installer:

```powershell
npm run electron:build
```

The installer is generated in:

```text
flex-web\dist\
```

Example:

```text
FlexRoute Setup 0.0.0.exe
```

---

# Common Problems

## Docker command hangs or Docker Desktop does not open

Check that the drive containing Docker's data has enough free disk space.

Docker images, build cache, Ollama models, and volumes can consume many GB.

---

## AI does not respond

Check:

```powershell
docker compose ps
```

Then check backend logs:

```powershell
docker compose logs -f backend
```

Also verify the models:

```powershell
docker compose exec ollama ollama list
```

---

## Backend cannot find Gemini API keys

Make sure:

```text
.env
```

exists in the FlexRoute project root.

Then recreate the backend:

```powershell
docker compose up -d --force-recreate backend
```

---

## Qdrant knowledge is missing

Run:

```powershell
docker compose exec backend python src/document_loader.py
```

---

# Quick Start Summary

For a new laptop:

```text
1. Install Docker Desktop
2. Copy the FlexRoute project
3. Place .env in the project root
4. Double-click setup.bat
5. Install FlexRoute Setup 0.0.0.exe
6. Double-click start_flexroute.bat
7. Use FlexRoute
```

For normal daily use after setup:

```text
Double-click start_flexroute.bat
```

That's it.
