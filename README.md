# FlexRoute — AI Fitness Coach & Dynamic Routine Architect

FlexRoute is a fully containerized AI fitness application built as a desktop experience with Electron + React and a Python/FastAPI backend.

It uses a hybrid AI architecture that routes lightweight fitness conversations to a local Mistral model through Ollama, while more complex routine-generation tasks can use Google Gemini. FlexRoute also combines injury-aware guardrails, persistent athlete state, and a Qdrant-powered RAG biomechanics layer.

## ✨ Core Features

- 🧠 **Semantic Routing / Hybrid AI**
  - Uses LangGraph to classify user intent.
  - Casual fitness chat and Q&A can be handled locally by Mistral through Ollama.
  - More complex routine-generation logic can be routed to Gemini 2.5 Flash.
- 🛡️ **Injury-Aware Guardrails**
  - Users can report injuries in natural language.
  - Injury information is stored locally and can influence future exercise selection.
- 🏗️ **Dynamic Routine Architecture**
  - Programming logic can adapt to training style, goals, and available context.
- 📚 **RAG Biomechanics Engine**
  - Uses Qdrant for vector search.
  - Uses `nomic-embed-text` for embeddings.
  - Relevant exercise cues and biomechanics knowledge can be injected into AI responses.
- 💾 **Persistent Local State**
  - SQLite stores application state and athlete/profile information.
  - Qdrant data and Ollama models are persisted using Docker volumes.
- 🐳 **Dockerized Backend Stack**
  - FastAPI backend
  - Ollama
  - Mistral
  - nomic-embed-text
  - Qdrant
- 🖥️ **Packaged Desktop App**
  - React + Vite frontend
  - Electron desktop shell
  - Windows installer generated using electron-builder

## 🛠️ Tech Stack

### Frontend
- React
- Vite
- Electron
- Tailwind CSS
- Framer Motion

### Backend
- Python
- FastAPI
- LangGraph
- LangChain
- SQLite
- Google Gemini 2.5 Flash

### Local AI / RAG
- Ollama
- Mistral
- nomic-embed-text
- Qdrant

### Deployment
- Docker
- Docker Compose
- electron-builder

## 🏗️ Architecture

```text
FlexRoute Desktop App
        |
        v
http://localhost:8000
        |
        v
FastAPI + LangGraph
   |             |
   |             |
   v             v
Ollama         Qdrant
   |
   +-- Mistral
   |
   +-- nomic-embed-text

        +
        |
        v
Google Gemini
(for configured cloud-routing tasks)
```

Docker Compose runs the backend services:

```text
flexroute-api
flexroute-qdrant
flexroute-ollama
```

## ⚙️ Requirements

For the Docker version, normal users do **not** need to manually install Python, Ollama, Qdrant, or backend dependencies.

You need:

1. **Docker Desktop**
2. The FlexRoute project repository
3. A valid `.env` file containing the required Gemini API keys
4. The packaged FlexRoute Windows installer

> Docker images and local AI models require several GB of disk space. Make sure the drive used by Docker Desktop has enough free storage before the first setup.

## 🚀 Docker Version — First-Time Setup

### 1. Clone the Docker repository

```powershell
git clone https://github.com/Fenry819/flexroute-ai-fitness-docker.git
cd flexroute-ai-fitness-docker
```

### 2. Configure environment variables

Create a file named `.env` in the project root:

```env
GOOGLE_API_KEY=your_primary_gemini_api_key_here
GOOGLE_API_KEY_BACKUP=your_backup_gemini_api_key_here
```

Do not commit `.env` to GitHub.

### 3. Make sure Docker Desktop is running

Verify:

```powershell
docker info
```

If Docker returns both Client and Server information, it is ready.

### 4. Run the automated setup

Double-click:

```text
setup.bat
```

or run:

```powershell
.\setup.bat
```

The setup script will:

1. Build/start the Docker services
2. Pull the Ollama Docker image if needed
3. Pull the `mistral` model
4. Pull the `nomic-embed-text` embedding model
5. Prepare the Qdrant knowledge collection

The first setup can take some time because several large Docker images and AI models need to be downloaded.

### 5. Install the FlexRoute desktop app

Run:

```text
FlexRoute Setup 0.0.0.exe
```

The app is normally installed under:

```text
%LOCALAPPDATA%\Programs\FlexRoute\
```

## 🎮 Normal Usage

After the first-time setup, you do not need to manually start Python, Ollama, FastAPI, or Qdrant.

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
Launch FlexRoute.exe
```

## 🐳 Useful Docker Commands

Check running services:

```powershell
docker compose ps
```

Expected services:

```text
flexroute-api
flexroute-qdrant
flexroute-ollama
```

Start services manually:

```powershell
docker compose up -d
```

Stop services:

```powershell
docker compose down
```

Avoid `docker compose down -v` unless you intentionally want to delete persistent Docker volumes.

View backend logs:

```powershell
docker compose logs -f backend
```

## 🤖 Ollama Models

Check installed models:

```powershell
docker compose exec ollama ollama list
```

Expected:

```text
mistral:latest
nomic-embed-text:latest
```

If required, pull them manually:

```powershell
docker compose exec ollama ollama pull mistral
docker compose exec ollama ollama pull nomic-embed-text
```

You do **not** need to run Ollama separately on Windows.

## 📚 Rebuild the Qdrant Knowledge Base

```powershell
docker compose exec backend python src/document_loader.py
```

This rebuilds the `exercise_cues` collection from the project's knowledge files.

## 💾 Persistent Data

Qdrant data is stored in the Docker volume:

```text
qdrant_data
```

Ollama models are stored in:

```text
ollama_data
```

FlexRoute uses:

```text
checkpoints.sqlite
```

for local state/profile persistence. The database is intentionally excluded from Git so personal user data is not committed.

## 🖥️ Development Setup

For frontend development:

```powershell
cd flex-web
npm install
npm run electron:dev
```

To build a new Windows installer:

```powershell
npm run electron:build
```

The generated installer appears in:

```text
flex-web\dist\
```

## 🔐 Security Notes

Never commit:

```text
.env
checkpoints.sqlite
*.db
*.sqlite
*.sqlite3
```

The repository should contain an `.env.example` instead of real API keys.

## 🧹 Recommended `.gitignore`

```gitignore
.env
venv/
__pycache__/
*.pyc
node_modules/
flex-web/node_modules/
flex-web/dist/
checkpoints.sqlite
*.db
*.sqlite
*.sqlite3
abort_signal.tmp
temp_*
desktop_app.py
.vscode/
.idea/
.DS_Store
Thumbs.db
```

## 🧪 Troubleshooting

### Docker Desktop is not running

Start Docker Desktop and wait until Docker is ready, then run:

```powershell
docker compose up -d
```

### AI responses are not working

```powershell
docker compose ps
docker compose logs -f backend
docker compose exec ollama ollama list
```

### Gemini API calls fail

Make sure `.env` exists in the project root and contains valid API keys, then run:

```powershell
docker compose up -d --force-recreate backend
```

### RAG / biomechanics responses are missing

```powershell
docker compose exec backend python src/document_loader.py
```

### Docker consumes too much C: drive space

Docker Desktop can store its Linux disk image on the system drive by default. If C: is small, move Docker's disk image location to another drive before downloading large models.

## 📦 New-Laptop Quick Start

```text
1. Install Docker Desktop
2. Clone the repository
3. Create the .env file
4. Run setup.bat
5. Install FlexRoute Setup 0.0.0.exe
6. Run start_flexroute.bat
7. Use FlexRoute
```

After initial setup, normal startup is simply:

```text
start_flexroute.bat
```

## 🤝 Disclaimer

FlexRoute is an AI-powered software project created to demonstrate hybrid local/cloud LLM routing, LangGraph orchestration, RAG, Docker deployment, and full-stack desktop integration.

AI-generated fitness and biomechanics information should not be treated as a substitute for professional medical diagnosis, treatment, rehabilitation, or clinical advice.

## 📄 License

Add the license used for this repository here.
