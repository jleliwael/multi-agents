"""Outil d'extraction et de découpage documentaire haute fidélité.

Supporte :
- PDF : extraction page par page via PyMuPDF (fitz)
- DOCX : extraction structurée des paragraphes et tableaux via python-docx
- XLSX : extraction des feuilles de calcul via openpyxl
Conserve systématiquement le nom de fichier et le numéro de page/section,
et découpe les contenus volumineux pour respecter la fenêtre de contexte.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional
import json

from config import settings
from tools.registry import tool


@dataclass
class DocumentChunk:
    """Morceau de document extrait avec métadonnées rigoureuses."""
    source_file: str
    file_type: str
    page_number: int
    chunk_index: int
    content: str
    char_count: int


def _resolve_doc_path(filepath: str) -> Path:
    """Résout le chemin d'un document dans les dossiers autorisés ou absolu."""
    p = Path(filepath)
    if not p.is_absolute():
        candidates = [
            settings.documents_dir / p,
            settings.uploads_dir / p,
            settings.workspace_dir / p,
            Path("tests/fixtures") / p,
            settings.base_dir / p,
        ]
        for c in candidates:
            if c.exists():
                return c.resolve()
        return (settings.documents_dir / p).resolve()
    return p.resolve()


def _chunk_text(text: str, max_chars: int = 2000, overlap: int = 200) -> List[str]:
    """Découpe un texte volumineux en morceaux avec chevauchement (overlap)."""
    clean_text = text.strip()
    if len(clean_text) <= max_chars:
        return [clean_text] if clean_text else []

    chunks: List[str] = []
    start = 0
    while start < len(clean_text):
        end = start + max_chars
        chunk = clean_text[start:end]
        chunks.append(chunk.strip())
        start = end - overlap
        if start >= len(clean_text):
            break
    return chunks


def extract_pdf_pages(file_path: Path) -> List[DocumentChunk]:
    """Extrait le texte d'un PDF page par page via PyMuPDF (fitz).

    Gère deux cas particuliers sans planter le pipeline :
    - PDF scanné (aucun texte extractible) : retourne un chunk signalé comme scanné.
    - PDF corrompu ou illisible : retourne un chunk d'erreur et continue.
    """
    chunks: List[DocumentChunk] = []
    try:
        import fitz  # PyMuPDF

        try:
            doc = fitz.open(file_path)
        except Exception as e:
            # Fichier corrompu ou format non reconnu
            chunks.append(DocumentChunk(
                source_file=file_path.name,
                file_type="pdf",
                page_number=1,
                chunk_index=1,
                content=f"[ERREUR DOCUMENT : Impossible d'ouvrir '{file_path.name}'. Fichier corrompu ou illisible. Détail : {e}]",
                char_count=0
            ))
            return chunks

        pages_with_text = 0
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            try:
                page_text = page.get_text("text").strip()
            except Exception:
                # Page individuelle illisible → on la passe
                continue

            page_num = page_idx + 1

            if not page_text:
                continue

            pages_with_text += 1
            sub_chunks = _chunk_text(page_text)
            for c_idx, sc in enumerate(sub_chunks, start=1):
                chunks.append(DocumentChunk(
                    source_file=file_path.name,
                    file_type="pdf",
                    page_number=page_num,
                    chunk_index=c_idx,
                    content=sc,
                    char_count=len(sc)
                ))

        # Si aucune page ne contenait du texte → PDF scanné sans couche OCR
        if pages_with_text == 0 and len(doc) > 0:
            chunks.append(DocumentChunk(
                source_file=file_path.name,
                file_type="pdf",
                page_number=1,
                chunk_index=1,
                content=(
                    f"[PDF SCANNÉ : Le document '{file_path.name}' ({len(doc)} page(s)) "
                    f"ne contient aucun texte extractible. "
                    f"Une reconnaissance optique de caractères (OCR) est nécessaire pour l'exploiter.]"
                ),
                char_count=0
            ))

        doc.close()

    except ImportError:
        # Fallback de secours si pymupdf n'est pas encore installé
        chunks.append(DocumentChunk(
            source_file=file_path.name,
            file_type="pdf",
            page_number=1,
            chunk_index=1,
            content=f"[Avertissement: PyMuPDF non installé. Fichier {file_path.name} détecté.]",
            char_count=50
        ))
    return chunks


def extract_docx_sections(file_path: Path) -> List[DocumentChunk]:
    """Extrait le texte d'un document Word (.docx) par section/paragraphes."""
    chunks: List[DocumentChunk] = []
    try:
        import docx
        doc = docx.Document(file_path)
        full_paragraphs = []
        for p in doc.paragraphs:
            txt = p.text.strip()
            if txt:
                full_paragraphs.append(txt)

        # Extraction des tableaux
        for table in doc.tables:
            table_rows = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                table_rows.append(" | ".join(cells))
            if table_rows:
                full_paragraphs.append("\n[Tableau]\n" + "\n".join(table_rows))

        combined_text = "\n\n".join(full_paragraphs)
        sub_chunks = _chunk_text(combined_text)
        for idx, sc in enumerate(sub_chunks, start=1):
            chunks.append(DocumentChunk(
                source_file=file_path.name,
                file_type="docx",
                page_number=idx,  # Équivalent de section/page estimée
                chunk_index=idx,
                content=sc,
                char_count=len(sc)
            ))
    except ImportError:
        chunks.append(DocumentChunk(
            source_file=file_path.name,
            file_type="docx",
            page_number=1,
            chunk_index=1,
            content=f"[Avertissement: python-docx non installé. Fichier {file_path.name} détecté.]",
            char_count=50
        ))
    return chunks


def extract_excel_sheets(file_path: Path) -> List[DocumentChunk]:
    """Extrait le contenu d'un fichier Excel (.xlsx) onglet par onglet."""
    chunks: List[DocumentChunk] = []
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=True)
        for sheet_idx, sheet_name in enumerate(wb.sheetnames, start=1):
            sheet = wb[sheet_name]
            rows_text = []
            for row in sheet.iter_rows(values_only=True):
                non_empty = [str(val).strip() for val in row if val is not None]
                if non_empty:
                    rows_text.append(" | ".join(non_empty))

            sheet_content = f"--- Onglet: {sheet_name} ---\n" + "\n".join(rows_text)
            sub_chunks = _chunk_text(sheet_content)
            for c_idx, sc in enumerate(sub_chunks, start=1):
                chunks.append(DocumentChunk(
                    source_file=file_path.name,
                    file_type="xlsx",
                    page_number=sheet_idx,
                    chunk_index=c_idx,
                    content=sc,
                    char_count=len(sc)
                ))
        wb.close()
    except ImportError:
        chunks.append(DocumentChunk(
            source_file=file_path.name,
            file_type="xlsx",
            page_number=1,
            chunk_index=1,
            content=f"[Avertissement: openpyxl non installé. Fichier {file_path.name} détecté.]",
            char_count=50
        ))
    return chunks


def extract_document(filepath: str) -> List[DocumentChunk]:
    """Point d'entrée universel d'extraction selon l'extension du fichier."""
    target_path = _resolve_doc_path(filepath)
    if not target_path.exists():
        raise FileNotFoundError(f"Fichier introuvable : '{filepath}' (résolu en '{target_path}')")

    ext = target_path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf_pages(target_path)
    elif ext in (".docx", ".doc"):
        return extract_docx_sections(target_path)
    elif ext in (".xlsx", ".xls"):
        return extract_excel_sheets(target_path)
    elif ext in (".txt", ".md", ".json", ".csv"):
        text = target_path.read_text(encoding="utf-8", errors="replace")
        sub_chunks = _chunk_text(text)
        return [
            DocumentChunk(
                source_file=target_path.name,
                file_type=ext.replace(".", ""),
                page_number=1,
                chunk_index=i,
                content=sc,
                char_count=len(sc)
            )
            for i, sc in enumerate(sub_chunks, start=1)
        ]
    else:
        raise ValueError(f"Format de fichier non supporté : '{ext}'")


@tool(name="read_document_pages", description="Extrait le texte d'un document (PDF, Word, Excel) page par page avec métadonnées exactes.")
def read_document_pages(filepath: str, max_pages: int = 5) -> str:
    """Lit les pages d'un document et retourne le texte indexé par page."""
    try:
        chunks = extract_document(filepath)
        if not chunks:
            return f"Le document '{filepath}' est vide ou ne contient aucun texte extractible."

        selected_chunks = chunks[:max_pages]
        formatted = []
        for c in selected_chunks:
            header = f"[Fichier: {c.source_file} | Page/Onglet: {c.page_number} | Morceau: {c.chunk_index}]"
            formatted.append(f"{header}\n{c.content}\n")

        résumé_total = f"--- Document '{filepath}' : {len(selected_chunks)} morceaux présentés sur {len(chunks)} extraits ---\n\n"
        return résumé_total + "\n".join(formatted)
    except Exception as e:
        return f"Erreur lors de la lecture du document '{filepath}' : {str(e)}"
