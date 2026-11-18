"""Stratégie de découpage documentaire en morceaux (Chunks) avec métadonnées rigoureuses.

Assure la conservation du nom de fichier, du numéro de page/section et
applique un chevauchement (overlap) glissant pour préserver le contexte sémantique.
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime, timezone
import hashlib


@dataclass
class DocumentChunk:
    """Morceau de document prêt pour vectorisation et indexation."""
    chunk_id: str
    text: str
    source_file: str
    file_type: str
    page_number: int
    chunk_index: int
    char_count: int
    created_at: str

    def to_metadata(self) -> Dict[str, Any]:
        """Convertit les métadonnées pour ChromaDB (types primitifs requis)."""
        return {
            "source_file": self.source_file,
            "file_type": self.file_type,
            "page_number": int(self.page_number),
            "chunk_index": int(self.chunk_index),
            "char_count": int(self.char_count),
            "created_at": self.created_at
        }


def compute_file_hash(file_path: Path) -> str:
    """Calcule l'empreinte MD5 d'un fichier pour détecter les modifications."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            hasher.update(block)
    return hasher.hexdigest()


def split_text_with_overlap(
    text: str,
    max_chars: int = 1500,
    overlap: int = 200
) -> List[str]:
    """Découpe un texte long avec fenêtre glissante de chevauchement."""
    clean = text.strip()
    if len(clean) <= max_chars:
        return [clean] if clean else []

    chunks: List[str] = []
    start = 0
    text_len = len(clean)

    while start < text_len:
        end = start + max_chars
        # Tentative de coupure sur un saut de ligne ou un point pour ne pas casser une phrase
        if end < text_len:
            split_pos = clean.rfind("\n", start + overlap, end)
            if split_pos == -1:
                split_pos = clean.rfind(". ", start + overlap, end)
            if split_pos != -1:
                end = split_pos + 1

        chunk_slice = clean[start:end].strip()
        if chunk_slice:
            chunks.append(chunk_slice)

        start = end - overlap
        if start >= text_len:
            break

    return chunks


def create_chunks_from_document_pages(
    pages: List[Dict[str, Any]],
    source_file: str,
    file_type: str,
    max_chars: int = 1500,
    overlap: int = 200
) -> List[DocumentChunk]:
    """Transforme une liste de pages extraites en objets DocumentChunk normés."""
    all_chunks: List[DocumentChunk] = []
    now_str = datetime.now(timezone.utc).isoformat()

    for p in pages:
        page_num = p.get("page_number", 1)
        raw_text = p.get("content", "").strip()
        if not raw_text:
            continue

        slices = split_text_with_overlap(raw_text, max_chars=max_chars, overlap=overlap)
        for c_idx, sc in enumerate(slices, start=1):
            chunk_unique_id = f"{source_file}_p{page_num}_c{c_idx}"
            all_chunks.append(DocumentChunk(
                chunk_id=chunk_unique_id,
                text=sc,
                source_file=source_file,
                file_type=file_type,
                page_number=page_num,
                chunk_index=c_idx,
                char_count=len(sc),
                created_at=now_str
            ))

    return all_chunks
