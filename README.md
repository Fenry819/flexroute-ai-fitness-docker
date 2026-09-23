# FlexRoute — AI Fitness Coach & Dynamic Routine Architect

FlexRoute is a fully containerized AI fitness application built as a desktop experience with Electron + React and a Python/FastAPI backend.

It uses a hybrid AI architecture: lightweight fitness chat and Q&A can run locally through Mistral + Ollama, while more complex routine-generation tasks can use Google Gemini. FlexRoute also includes injury-aware guardrails, persistent athlete state, and a Qdrant-powered RAG biomechanics layer.

---

## ✨ Core Features

- 🧠 **Hybrid AI / Semantic Routing**
  - LangGraph classifies user intent.
  - Casual fitness chat and Q&A can run locally through Mistral.
  - More complex routine-generation tasks can use Gemini 2.5 Flash.

- 🛡️ **Injury-Aware Guardrails**
  - Users can report injuries in natural language.
  - Injury information is stored persistently and can influence exercise selection.

- 🏗️ **Dynamic Routine Architecture**
  - Training plans can adapt to athlete profile, training style, goals, and injuries.

- 📚 **RAG Biomechanics Engine**
  - Qdrant stores vectorized knowledge.
  - `nomic-embed-text` generates embeddings.
  - Relevant biomechanics/form knowledge can be retrieved and added to AI context.

- 💾 **Persistent Data**
  - SQLite application/profile data is stored in a Docker named volume.
  - Qdrant data is stored in a Docker named volume.
  - Ollama models are stored in a Docker named volume.

- 🎮 **Automatic GPU / CPU Mode**
  - `setup.bat` and `start_flexroute.bat` detect NVIDIA GPUs automatically.
  - NVIDIA systems use the GPU Compose override.
  - Other systems fall back to CPU mode.

- 🖥️ **Packaged Windows Desktop App**
  - Electron + React + Vite.
  - Users can choose the installation directory.
  - The launcher opens the installed app through its Windows shortcut instead of relying on a fixed install path.

---

# 🛠️ Tech Stack

## Frontend
- React
- Vite
- Electron
- Tailwind CSS
- Framer Motion

## Backend
- Python
- FastAPI
- LangGraph
- LangChain
- SQLite
- Google Gemini 2.5 Flash

## Local AI / RAG
- Ollama
- Mistral
- nomic-embed-text
- Qdrant

## Deployment
- Docker
- Docker Compose
- electron-builder / NSIS

---

# 🏗️ Architecture

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

Docker Compose runs:

```text
flexroute-api
flexroute-qdrant
flexroute-ollama
```

Persistent Docker volumes:

```text
sqlite_data
qdrant_data
ollama_data
```

---

# ⚙️ Requirements

For normal use, you do **not** need to manually install Python, Ollama, Qdrant, or Node.js.

You need:

1. **Docker Desktop**
2. The FlexRoute repository
3. A valid `.env` file containing your Gemini API keys
4. The FlexRoute Windows installer from the repository's **GitHub Releases** page

> Docker images and local AI models require several GB of disk space. If your C: drive is small, move Docker Desktop's disk image location to another drive before the first setup.

---

# 🚀 First-Time Setup

## 1. Clone the repository

```powershell
git clone https://github.com/Fenry819/flexroute-ai-fitness-docker.git
cd flexroute-ai-fitness-docker
```

## 2. Create the `.env` file

Create a file named:

```text
.env
```

in the project root.

Example:

```env
GOOGLE_API_KEY=your_primary_gemini_api_key_here
GOOGLE_API_KEY_BACKUP=your_backup_gemini_api_key_here
```

Never commit `.env` to GitHub.

## 3. Install and start Docker Desktop

Verify Docker:

```powershell
docker info
```

If Docker returns both Client and Server information, it is ready.

## 4. Download the FlexRoute Windows installer

Open the repository's **Releases** section on GitHub and download the latest installer:

```text
FlexRoute Setup <version>.exe
```

The installer is distributed through GitHub Releases instead of being committed directly to the repository because Electron installers are large generated build artifacts.

## 5. Run the automated backend setup

Double-click:

```text
setup.bat
```

or run:

```powershell
.\setup.bat
```

The setup script will:

1. Check that Docker is available.
2. Detect whether an NVIDIA GPU is available.
3. Start FlexRoute in GPU mode when NVIDIA is available, otherwise CPU mode.
4. Build/start the Docker services.
5. Pull the Mistral model.
6. Pull `nomic-embed-text`.
7. Prepare the Qdrant knowledge collection.

The first run can take a while because Docker images and AI models need to be downloaded.

### NVIDIA systems

When an NVIDIA GPU is detected, FlexRoute combines:

```text
docker-compose.yml
+
docker-compose.gpu.yml
```

so Ollama can use the NVIDIA GPU.

### CPU-only / non-NVIDIA systems

The normal:

```text
docker-compose.yml
```

is used without the GPU override.

## 6. Install FlexRoute

Run the downloaded installer:

```text
FlexRoute Setup <version>.exe
```

The installer allows you to choose where FlexRoute is installed.

It creates Windows shortcuts that `start_flexroute.bat` can use, so the launcher does not depend on a hardcoded installation directory.

---

# 🎮 Normal Usage

After the first-time setup, run:

```text
start_flexroute.bat
```

The launcher will:

```text
Check Docker
      ↓
Detect NVIDIA GPU
      ↓
Start Docker services in GPU or CPU mode
      ↓
Wait for the backend
      ↓
Find the FlexRoute Windows shortcut
      ↓
Launch FlexRoute
```

You do **not** need to manually run:

```text
ollama serve
python server.py
npm run electron:dev
```

for normal use.

---

# 🐳 Docker Files

## `docker-compose.yml`

Defines the normal FlexRoute stack:

- FastAPI backend
- Qdrant
- Ollama
- persistent SQLite/Qdrant/Ollama volumes

## `docker-compose.gpu.yml`

Adds NVIDIA GPU access to the Ollama service.

It is used automatically by the batch scripts when `nvidia-smi` detects an NVIDIA GPU.

---

# 💾 Persistent Data

## SQLite

Application/profile data is stored in:

```text
sqlite_data
```

The backend uses:

```text
/app/data/checkpoints.sqlite
```

inside the container.

This means a fresh clone does **not** need a pre-existing `checkpoints.sqlite` file on Windows.

## Qdrant

Stored in:

```text
qdrant_data
```

## Ollama models

Stored in:

```text
ollama_data
```

Named volumes survive normal container recreation.

Avoid:

```powershell
docker compose down -v
```

unless you intentionally want to delete persistent data and downloaded models.

---

# 🎮 NVIDIA GPU Verification

To check whether Mistral is currently loaded on the GPU:

```powershell
docker compose exec ollama ollama ps
```

When GPU acceleration is active, the `PROCESSOR` column may show:

```text
100% GPU
```

To verify the NVIDIA driver on Windows:

```powershell
nvidia-smi
```

> Windows Task Manager GPU numbering and NVIDIA device numbering are not necessarily the same. Windows may call an Intel iGPU `GPU 0` and the NVIDIA GPU `GPU 1`, while NVIDIA/Docker sees the NVIDIA card as device `0`.

---

# 📚 Qdrant Knowledge Base

To rebuild the RAG collection manually:

```powershell
docker compose exec backend python src/document_loader.py
```

This rebuilds the:

```text
exercise_cues
```

collection from the project's knowledge files.

---

# 🐳 Useful Docker Commands

Check services:

```powershell
docker compose ps
```

Expected containers:

```text
flexroute-api
flexroute-qdrant
flexroute-ollama
```

Start CPU/default mode manually:

```powershell
docker compose up -d
```

Start NVIDIA GPU mode manually:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

Stop services:

```powershell
docker compose down
```

View backend logs:

```powershell
docker compose logs -f backend
```

Check installed Ollama models:

```powershell
docker compose exec ollama ollama list
```

Expected models:

```text
mistral:latest
nomic-embed-text:latest
```

---

# 🖥️ Development Setup

Node.js/npm are only required if you are developing or rebuilding the Electron frontend.

```powershell
cd flex-web
npm install
npm run electron:dev
```

To create a new Windows installer:

```powershell
npm run electron:build
```

Generated output appears under:

```text
flex-web\dist\
```

`flex-web/dist/` remains ignored by Git because it contains generated build artifacts.

For distribution, upload the final installer to **GitHub Releases**.

---

# 🔐 Security / Git Notes

Never commit:

```text
.env
*.db
*.sqlite
*.sqlite3
```

Also keep generated Electron output ignored:

```gitignore
flex-web/dist/
```

Recommended `.gitignore` entries:

```gitignore
.env

venv/
__pycache__/
*.pyc

node_modules/
flex-web/node_modules/

flex-web/dist/

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

---

# 🧪 Troubleshooting

## Docker Desktop is not running

Start Docker Desktop and verify:

```powershell
docker info
```

## Backend is not running

```powershell
docker compose ps
docker compose logs backend
```

## AI does not respond

```powershell
docker compose ps
docker compose exec ollama ollama list
docker compose logs -f backend
```

## Mistral is using CPU instead of NVIDIA GPU

Verify:

```powershell
nvidia-smi
```

Then start GPU mode manually:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

Run a Mistral request and check:

```powershell
docker compose exec ollama ollama ps
```

Look for:

```text
100% GPU
```

## Gemini API calls fail

Verify that `.env` exists in the project root and contains valid keys.

Then recreate the backend:

```powershell
docker compose up -d --force-recreate backend
```

## RAG / biomechanics responses are missing

```powershell
docker compose exec backend python src/document_loader.py
```

## Docker consumes too much C: drive space

Docker Desktop may store its Linux virtual disk on C: by default.

Docker images, Mistral, Ollama data, Qdrant data, and build cache can consume many GB.

If C: has limited space, move Docker Desktop's disk image location to another drive before downloading the models.

---

# 📦 New-Laptop Quick Start

```text
1. Install Docker Desktop
2. Clone the FlexRoute repository
3. Add the .env file
4. Download the latest FlexRoute installer from GitHub Releases
5. Run setup.bat
6. Install FlexRoute wherever you want
7. Run start_flexroute.bat
8. Use FlexRoute
```

After first-time setup, normal use is simply:

```text
start_flexroute.bat
```

---

# 🤝 Disclaimer

FlexRoute is an AI-powered software project created to demonstrate hybrid local/cloud LLM routing, LangGraph orchestration, RAG, Docker deployment, GPU acceleration, and full-stack desktop integration.

AI-generated fitness and biomechanics information should not be treated as a substitute for professional medical diagnosis, treatment, rehabilitation, or clinical advice.

---

# 📄 License

Add the license used for this repository here.
