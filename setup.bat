@echo off
title FlexRoute Setup

echo.
echo ==========================
echo   FlexRoute Setup
echo ==========================
echo.

echo Starting Docker services...
docker compose up -d --build

echo.
echo Pulling Mistral model...
docker compose exec ollama ollama pull mistral

echo.
echo Pulling embedding model...
docker compose exec ollama ollama pull nomic-embed-text

echo.
echo Preparing Qdrant knowledge base...
docker compose exec backend python src/document_loader.py

echo.
echo ==========================
echo   FlexRoute setup complete
echo ==========================
echo.
echo You can now install/open FlexRoute.
echo.

pause