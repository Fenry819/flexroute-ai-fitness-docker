# src/document_loader.py
import os
import glob
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from dotenv import load_dotenv

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "exercise_cues"
KNOWLEDGE_DIR = "knowledge"

def process_knowledge_base():
    if not os.path.exists(KNOWLEDGE_DIR):
        print(f"❌ Error: '{KNOWLEDGE_DIR}' folder does not exist.")
        return

    all_documents = []
    
    # 1. LOAD TEXT FILES
    for file_path in glob.glob(os.path.join(KNOWLEDGE_DIR, "*.txt")):
        print(f"📄 Loading: {os.path.basename(file_path)}...")
        all_documents.extend(TextLoader(file_path, encoding='utf-8').load())

    # 2. LOAD CSV (ALL ROWS - NO LIMITS NEEDED LOCALLY)
    for file_path in glob.glob(os.path.join(KNOWLEDGE_DIR, "*.csv")):
        print(f"📊 Loading: {os.path.basename(file_path)}...")
        all_documents.extend(CSVLoader(file_path=file_path, encoding='utf-8').load())

    print(f"✅ Total raw document objects loaded: {len(all_documents)}")

    # 3. CHUNKING
    print("✂️ Slicing data into optimal RAG chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunked_documents = text_splitter.split_documents(all_documents)
    print(f"✅ Generated {len(chunked_documents)} chunks.")

    # 4. LOCAL EMBEDDING ENGINE (UNLIMITED SPEED)
    print("🧠 Booting up Local Nomic Embedding Engine (Zero API Limits)...")
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

    embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url=OLLAMA_URL
    )
    
    print(f"💾 Ingesting {len(chunked_documents)} chunks into Qdrant at maximum CPU speed...")
    
    try:
        QdrantVectorStore.from_documents(
            chunked_documents,
            embeddings,
            url=QDRANT_URL,
            collection_name=COLLECTION_NAME,
            force_recreate=True, 
        )
        print("\n🚀 [Vector DB] SUCCESS! The God-Tier Knowledge Base is officially baked using Local AI.")
    except Exception as e:
        print(f"❌ Local Embedding Failed: {e}")

if __name__ == "__main__":
    process_knowledge_base()