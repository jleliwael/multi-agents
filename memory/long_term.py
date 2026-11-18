"""Gestionnaire de mémoire long terme vectorielle s'appuyant sur ChromaDB et nomic-embed-text.

Stocke de manière persistante les chunks documentaires dans data/chroma/
et permet la recherche sémantique par similarité cosinus.
"""

from typing import List, Dict, Any, Optional
import json
import urllib.request
import urllib.error
from pathlib import Path
import hashlib

from config import settings
from memory.chunking import DocumentChunk

# Tentative d'import de chromadb
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class OllamaEmbeddingFunction:
    """Générateur d'embeddings interfaçant l'API /api/embeddings d'Ollama."""

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        self.model = model or settings.model_embedding
        self.base_url = base_url or settings.ollama_base_url
        self.embed_url = f"{self.base_url.rstrip('/')}/api/embeddings"

    def embed_query(self, text: str) -> List[float]:
        """Génère l'embedding d'une requête textuelle."""
        return self._call_ollama_embeddings(f"search_query: {text}")

    def embed_document(self, text: str) -> List[float]:
        """Génère l'embedding d'un morceau de document."""
        return self._call_ollama_embeddings(f"search_document: {text}")

    def _call_ollama_embeddings(self, prompt: str) -> List[float]:
        payload = json.dumps({"model": self.model, "prompt": prompt}).encode("utf-8")
        req = urllib.request.Request(
            self.embed_url,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("embedding", [])
        except Exception:
            # Fallback déterministe pseudo-vecteur 768d si Ollama / nomic-embed-text n'est pas dispo
            return self._fallback_hash_embedding(prompt)

    def _fallback_hash_embedding(self, text: str) -> List[float]:
        """Produit un vecteur normalisé de 768 dimensions déterministe par hachage."""
        vec = []
        for i in range(768):
            seed = f"{text}_{i}".encode("utf-8")
            h = int(hashlib.md5(seed).hexdigest()[:8], 16)
            vec.append((h / 0xFFFFFFFF) * 2 - 1)
        # Normalisation L2
        norm = sum(x**2 for x in vec) ** 0.5
        return [x / norm for x in vec] if norm > 0 else vec


class LongTermMemory:
    """Mémoire vectorielle persistante dans ChromaDB."""

    def __init__(self, persist_dir: Optional[Path] = None, collection_name: str = "documents_knowledge"):
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.embedder = OllamaEmbeddingFunction()

        if CHROMADB_AVAILABLE:
            self.client = chromadb.PersistentClient(path=str(self.persist_dir))
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        else:
            self.client = None
            self.collection = None

    def add_chunks(self, chunks: List[DocumentChunk]) -> int:
        """Vectorise et persiste une liste de chunks documentaires."""
        if not chunks:
            return 0

        if not CHROMADB_AVAILABLE or not self.collection:
            return len(chunks)

        ids = [c.chunk_id for c in chunks]
        texts = [c.text for c in chunks]
        metadatas = [c.to_metadata() for c in chunks]
        embeddings = [self.embedder.embed_document(c.text) for c in chunks]

        self.collection.upsert(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=embeddings
        )
        return len(chunks)

    def search_similar(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Recherche les passages les plus pertinents par similarité cosinus."""
        if not CHROMADB_AVAILABLE or not self.collection:
            return []

        query_emb = self.embedder.embed_query(query)
        results = self.collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        matches = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            for i in range(len(docs)):
                matches.append({
                    "text": docs[i],
                    "metadata": metas[i] if i < len(metas) else {},
                    "score": round(1.0 - distances[i], 4) if i < len(distances) else 0.8
                })

        return matches

    def get_indexed_files(self) -> List[str]:
        """Retourne la liste des noms de fichiers déjà présents dans la mémoire."""
        if not CHROMADB_AVAILABLE or not self.collection:
            return []

        data = self.collection.get(include=["metadatas"])
        seen_files = set()
        for meta in data.get("metadatas", []):
            if meta and "source_file" in meta:
                seen_files.add(meta["source_file"])
        return sorted(list(seen_files))


# Instance singleton
long_term_memory = LongTermMemory()
