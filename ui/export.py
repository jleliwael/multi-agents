"""Conversion d'un rapport Markdown en document Word (.docx) pour le téléchargement.

Gère le sous-ensemble utilisé par les rapports : titres (#), listes (-, *, 1.),
tableaux Markdown, citations (>), gras (**texte**) et paragraphes.
"""

from __future__ import annotations

import io
import re
from typing import List

import docx
from docx.shared import Pt

_BOLD = re.compile(r"\*\*(.+?)\*\*")


def _add_inline(paragraph, text: str) -> None:
    """Ajoute du texte en gérant le gras **...** ; le reste du Markdown inline est retiré."""
    pos = 0
    for m in _BOLD.finditer(text):
        if m.start() > pos:
            paragraph.add_run(_clean(text[pos:m.start()]))
        paragraph.add_run(_clean(m.group(1))).bold = True
        pos = m.end()
    if pos < len(text):
        paragraph.add_run(_clean(text[pos:]))


def _clean(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1 (\2)", text)  # liens -> texte (url)
    return text.replace("`", "").replace("*", "")


def _is_table_sep(line: str) -> bool:
    return bool(re.fullmatch(r"\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*", line))


def _cells(line: str) -> List[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def markdown_to_docx(markdown: str, title: str = "") -> bytes:
    document = docx.Document()
    document.styles["Normal"].font.size = Pt(10.5)
    if title:
        document.core_properties.title = title

    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Tableau Markdown : ligne d'en-tête suivie d'une ligne de séparation
        if stripped.startswith("|") and i + 1 < len(lines) and _is_table_sep(lines[i + 1]):
            header = _cells(stripped)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            table = document.add_table(rows=1 + len(rows), cols=len(header))
            table.style = "Table Grid"
            for c, text in enumerate(header):
                cell = table.rows[0].cells[c]
                cell.text = ""
                cell.paragraphs[0].add_run(_clean(text)).bold = True
            for r, row in enumerate(rows, start=1):
                for c in range(len(header)):
                    table.rows[r].cells[c].text = _clean(row[c]) if c < len(row) else ""
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            document.add_heading(_clean(heading.group(2)), level=min(len(heading.group(1)), 4))
        elif re.match(r"^[-*+]\s+", stripped):
            _add_inline(document.add_paragraph(style="List Bullet"), re.sub(r"^[-*+]\s+", "", stripped))
        elif re.match(r"^\d+[.)]\s+", stripped):
            _add_inline(document.add_paragraph(style="List Number"), re.sub(r"^\d+[.)]\s+", "", stripped))
        elif stripped.startswith(">"):
            p = document.add_paragraph(style="Intense Quote")
            _add_inline(p, stripped.lstrip("> ").strip())
        elif re.fullmatch(r"-{3,}|\*{3,}", stripped):
            pass  # ligne horizontale : ignorée
        else:
            _add_inline(document.add_paragraph(), stripped)
        i += 1

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
