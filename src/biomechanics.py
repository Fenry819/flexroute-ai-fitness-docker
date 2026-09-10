# src/biomechanics.py
import os
from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from dotenv import load_dotenv

load_dotenv()

# 1. SETUP LOCAL EMBEDDING ENGINE
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url=OLLAMA_URL
)

# 2. DEFINING THE QDRANT STORAGE PATH
COLLECTION_NAME = "exercise_cues"

def search_biomechanics(query: str, k: int = 3):
    """Retrieves the most relevant form cues from our local massive database."""
    print(f"\n⚡ [Vector Search] Scanning Local God-Tier Database for: '{query}'...")
    
    try:
        qdrant = QdrantVectorStore.from_existing_collection(
            embedding=embeddings,
            collection_name=COLLECTION_NAME,
            url=QDRANT_URL,
        )
        
        # Retrieve the top 3 most relevant paragraphs
        results = qdrant.similarity_search(query, k=k)
        
        print(f"✅ [Vector Search] Found {len(results)} relevant chunks.")
        for i, res in enumerate(results):
            # Print a preview in the terminal so you can see what it found
            preview = res.page_content[:100].replace('\n', ' ') + "..."
            print(f"   -> Chunk {i+1}: {preview}")
            
        return results
    except Exception as e:
        print(f"❌ [Vector Search] Local Qdrant read error: {e}")
        return []

if __name__ == "__main__":
    # A quick test to check if this is working
    test_query = "What should I do with my shoulder blades when I train chest?"
    search_biomechanics(test_query)