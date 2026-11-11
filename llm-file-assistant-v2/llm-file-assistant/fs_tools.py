"""
fs_tools.py - File system tools exposed to the LLM.

Each tool returns a JSON-serializable structure so it can be passed back to
the model as a tool result. Tools never raise on expected failures
(missing file, bad type, etc.); they return {"success": False, "error": ...}.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any, Callable

SUPPORTED_READ_EXTENSIONS = {".txt", ".pdf", ".docx"}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _ok(**kwargs: Any) -> dict:
    return {"success": True, **kwargs}


def _err(message: str, **kwargs: Any) -> dict:
    return {"success": False, "error": message, **kwargs}


def _normalize_ext(extension: str) -> str:
    ext = extension.strip().lower()
    return ext if ext.startswith(".") else f".{ext}"


def _file_metadata(path: Path) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path.resolve()),
        "extension": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "modified": dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


# --------------------------------------------------------------------------- #
# Text extractors (one per supported format)
# --------------------------------------------------------------------------- #
def _extract_txt(path: Path) -> tuple[str, dict]:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=encoding), {"encoding": encoding}
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode text file")  # unreachable: latin-1 never fails


def _extract_pdf(path: Path) -> tuple[str, dict]:
    from pypdf import PdfReader  # imported lazily so missing deps give a clear error

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages), {"pages": len(pages)}


def _extract_docx(path: Path) -> tuple[str, dict]:
    from docx import Document

    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:  # resumes often put skills in tables
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(parts), {"paragraphs": len(doc.paragraphs), "tables": len(doc.tables)}


_EXTRACTORS: dict[str, Callable[[Path], tuple[str, dict]]] = {
    ".txt": _extract_txt,
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
}


# --------------------------------------------------------------------------- #
# Tool 1: read_file
# --------------------------------------------------------------------------- #
def read_file(filepath: str) -> dict:
    """Read a resume (PDF, TXT, DOCX) and return its text plus metadata."""
    try:
        path = Path(filepath).expanduser()

        # Validation
        if not path.exists():
            return _err(f"File not found: {filepath}")
        if not path.is_file():
            return _err(f"Not a file: {filepath}")

        ext = path.suffix.lower()
        if ext not in SUPPORTED_READ_EXTENSIONS:
            return _err(
                f"Unsupported file type '{ext}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_READ_EXTENSIONS))}"
            )
        if path.stat().st_size == 0:
            return _err("File is empty", metadata=_file_metadata(path))

        # Extraction
        text, extra = _EXTRACTORS[ext](path)
        text = text.strip()
        if not text:
            return _err(
                "No extractable text found (scanned PDF? OCR is required)",
                metadata=_file_metadata(path),
            )

        metadata = {**_file_metadata(path), **extra, "word_count": len(text.split())}
        return _ok(content=text, metadata=metadata)

    except ImportError as exc:
        return _err(f"Missing dependency: {exc}. Run: pip install -r requirements.txt")
    except Exception as exc:  # corrupted files, permission errors, etc.
        return _err(f"Failed to read '{filepath}': {exc}")


# --------------------------------------------------------------------------- #
# Tool 2: list_files
# --------------------------------------------------------------------------- #
def list_files(directory: str, extension: str | None = None) -> list[dict]:
    """
    List files in a directory with name, size, and modified date.
    Optionally filter by extension (e.g. '.pdf' or 'pdf').
    Raises NotADirectoryError if the directory is missing; the caller
    (the assistant's dispatcher) converts that into a tool error.
    """
    base = Path(directory).expanduser()
    if not base.is_dir():
        raise NotADirectoryError(f"Directory not found: {directory}")

    ext = _normalize_ext(extension) if extension else None
    return [
        _file_metadata(p)
        for p in sorted(base.iterdir())
        if p.is_file() and (ext is None or p.suffix.lower() == ext)
    ]


# --------------------------------------------------------------------------- #
# Tool 3: write_file
# --------------------------------------------------------------------------- #
def write_file(filepath: str, content: str) -> dict:
    """Write UTF-8 text to a file, creating parent directories as needed."""
    try:
        path = Path(filepath).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return _ok(
            path=str(path.resolve()),
            bytes_written=len(content.encode("utf-8")),
        )
    except Exception as exc:
        return _err(f"Failed to write '{filepath}': {exc}")


# --------------------------------------------------------------------------- #
# Tool 4: search_in_file
# --------------------------------------------------------------------------- #
def search_in_file(filepath: str, keyword: str, context_lines: int = 1) -> dict:
    """
    Case-insensitive keyword search. Returns each matching line with
    `context_lines` lines before and after it.
    """
    if not keyword or not keyword.strip():
        return _err("Keyword must be a non-empty string")

    read = read_file(filepath)
    if not read["success"]:
        return read  # propagate the read error unchanged

    lines = read["content"].splitlines()
    pattern = re.compile(re.escape(keyword.strip()), re.IGNORECASE)
    context_lines = max(0, int(context_lines))

    matches = []
    for idx, line in enumerate(lines):
        match = pattern.search(line)
        if match:
            start = max(0, idx - context_lines)
            end = min(len(lines), idx + context_lines + 1)
            matches.append({
                "line_number": idx + 1,
                "column": match.start() + 1,
                "line": line.strip(),
                "context": "\n".join(lines[start:end]),
            })

    return _ok(
        filepath=read["metadata"]["path"],
        keyword=keyword,
        match_count=len(matches),
        matches=matches,
    )


# --------------------------------------------------------------------------- #
# Tool registry: schemas (for the LLM) and callables (for execution)
# --------------------------------------------------------------------------- #
TOOL_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "read_file": read_file,
    "list_files": list_files,
    "write_file": write_file,
    "search_in_file": search_in_file,
}

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "read_file",
        "description": (
            "Read a resume file (.pdf, .txt, or .docx) and return its extracted "
            "text and metadata. Use this before summarizing or analyzing a resume."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Path to the file."},
            },
            "required": ["filepath"],
        },
    },
    {
        "name": "list_files",
        "description": (
            "List files in a directory with name, size, and modified date. "
            "Optionally filter by extension such as '.pdf' or '.txt'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory path."},
                "extension": {
                    "type": "string",
                    "description": "Optional extension filter, e.g. '.pdf'.",
                },
            },
            "required": ["directory"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write text content to a file, creating parent directories if needed. "
            "Use this to save summaries or reports."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Destination path."},
                "content": {"type": "string", "description": "Text to write."},
            },
            "required": ["filepath", "content"],
        },
    },
    {
        "name": "search_in_file",
        "description": (
            "Search a resume for a keyword (case-insensitive). Returns matching "
            "lines with surrounding context. Useful for skills such as 'Python'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "File to search."},
                "keyword": {"type": "string", "description": "Keyword to find."},
                "context_lines": {
                    "type": "integer",
                    "description": "Lines of context before and after each match (default 1).",
                    "default": 1,
                },
            },
            "required": ["filepath", "keyword"],
        },
    },
]
