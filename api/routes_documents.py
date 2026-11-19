"""Routes de la bibliothèque de documents (mémoire long terme ChromaDB)."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.routes_tasks import save_upload
from api.schemas import DocumentInfo
from config import settings
from memory.long_term import long_term_memory
from scripts.index_docs import index_file

router = APIRouter(tags=["bibliothèque"])


@router.get("/documents", response_model=List[DocumentInfo], summary="Documents de la bibliothèque")
def list_documents():
    folder = settings.documents_dir
    folder.mkdir(parents=True, exist_ok=True)
    indexed = set(long_term_memory.get_indexed_files())
    return [
        DocumentInfo(name=p.name, size_kb=round(p.stat().st_size / 1024, 1), indexed=p.name in indexed)
        for p in sorted(folder.iterdir()) if p.is_file()
    ]


@router.post("/documents", summary="Ajouter un document et l'indexer")
def add_document(file: UploadFile = File(...)):
    path = save_upload(file, settings.documents_dir)
    try:
        chunks = index_file(path)
    except Exception as exc:
        raise HTTPException(500, f"Document enregistré mais non indexé : {type(exc).__name__} : {exc}")
    return {"name": path.name, "chunks_indexed": chunks}


@router.post("/documents/{name}/index", summary="(Ré)indexer un document déjà présent")
def reindex_document(name: str):
    path = settings.documents_dir / name
    if path.name != name or not path.is_file():
        raise HTTPException(404, "Document introuvable.")
    long_term_memory.delete_file(name)
    return {"name": name, "chunks_indexed": index_file(path)}


@router.delete("/documents/{name}/index", summary="Retirer un document de l'index (le fichier est conservé)")
def unindex_document(name: str):
    removed = long_term_memory.delete_file(name)
    return {"name": name, "chunks_removed": removed}
