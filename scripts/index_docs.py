"""Script d'indexation incrémentale du dossier data/documents dans ChromaDB.

Parcourt tous les documents supportés (PDF, DOCX, XLSX, TXT),
ignore les fichiers déjà indexés sans modification, et persiste
les nouveaux chunks vectorisés dans la mémoire long terme.
"""

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings
from tools.documents import extract_document
from memory.chunking import create_chunks_from_document_pages
from memory.long_term import long_term_memory


def index_file(file_path: Path) -> int:
    """Indexe un seul document dans ChromaDB et retourne le nombre de morceaux ajoutés."""
    raw_chunks = extract_document(str(file_path))
    pages_data = [{"page_number": rc.page_number, "content": rc.content} for rc in raw_chunks]
    chunks = create_chunks_from_document_pages(
        pages=pages_data,
        source_file=file_path.name,
        file_type=file_path.suffix.lower().replace(".", ""),
    )
    return long_term_memory.add_chunks(chunks)


def index_documents_directory() -> None:
    print("=" * 70)
    print("      INDEXATION INCRÉMENTALE DANS CHROMADB (MÉMOIRE LONG TERME)      ")
    print("=" * 70)

    doc_dir = settings.documents_dir
    doc_dir.mkdir(parents=True, exist_ok=True)

    # Récupération des fichiers déjà indexés
    already_indexed = set(long_term_memory.get_indexed_files())
    print(f"Dossier source : {doc_dir}")
    print(f"Fichiers déjà indexés en base : {len(already_indexed)} {list(already_indexed)}")
    print("-" * 70)

    supported_exts = {".pdf", ".docx", ".xlsx", ".txt", ".md", ".csv"}
    all_files = [f for f in doc_dir.iterdir() if f.is_file() and f.suffix.lower() in supported_exts]

    if not all_files:
        print(f"Aucun document trouvé dans {doc_dir}. Dépose des fichiers pour les indexer.")
        return

    new_indexed_count = 0
    total_chunks_added = 0

    for file_path in all_files:
        if file_path.name in already_indexed:
            print(f"-> [IGNORÉ] Déjà indexé : {file_path.name}")
            continue

        print(f"-> [INDEXATION] Traitement de : {file_path.name}...")
        try:
            # 1. Extraction brute page par page
            raw_chunks = extract_document(str(file_path))
            pages_data = [
                {"page_number": rc.page_number, "content": rc.content}
                for rc in raw_chunks
            ]

            # 2. Découpage régulier avec métadonnées et chevauchement
            chunks = create_chunks_from_document_pages(
                pages=pages_data,
                source_file=file_path.name,
                file_type=file_path.suffix.lower().replace(".", "")
            )

            # 3. Vectorisation et stockage dans ChromaDB
            added = long_term_memory.add_chunks(chunks)
            total_chunks_added += added
            new_indexed_count += 1
            print(f"   Succès : {added} morceaux indexés pour {file_path.name}.")

        except Exception as e:
            print(f"   [ERREUR] Échec de l'indexation de {file_path.name} : {e}")

    print("=" * 70)
    print(f"Bilan : {new_indexed_count} nouveaux fichiers indexés ({total_chunks_added} morceaux vectorisés).")
    print("=" * 70)


if __name__ == "__main__":
    index_documents_directory()
