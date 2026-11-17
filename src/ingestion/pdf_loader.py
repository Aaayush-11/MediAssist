from __future__ import annotations

from pathlib import Path
from typing import Any

import pdfplumber


class PDFLoadError(Exception):
    """Raised when a PDF cannot be opened or read."""


class PDFLoader:
    """Extracts text from PDF files page by page using pdfplumber."""

    def load_pdf(self, file_path: str | Path) -> list[dict[str, Any]]:
        """Extract non-blank page text from a PDF.

        Args:
            file_path: Path to a ``.pdf`` file.

        Returns:
            A list of dicts with ``source`` (filename), ``page`` (1-based page
            number in the original document) and ``text``. Pages with no text
            or only whitespace are skipped; original page numbers are preserved.

        Raises:
            TypeError: If ``file_path`` is not a string or Path.
            FileNotFoundError: If the path does not exist or is not a file.
            ValueError: If the file does not have a ``.pdf`` extension.
            PDFLoadError: If the PDF is invalid, corrupted, or unreadable.
        """
        if not isinstance(file_path, (str, Path)):
            raise TypeError(
                f"file_path must be a str or Path, got {type(file_path).__name__}."
            )

        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            raise ValueError(
                f"Invalid file extension '{path.suffix}' for {path}; expected '.pdf'."
            )
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")
        if not path.is_file():
            raise FileNotFoundError(f"Path is not a file: {path}")

        pages: list[dict[str, Any]] = []
        try:
            with pdfplumber.open(path) as pdf:
                for page_number, page in enumerate(pdf.pages, start=1):
                    try:
                        text = page.extract_text()
                    except Exception as exc:
                        raise PDFLoadError(
                            f"Failed to extract text from page {page_number} of {path.name}: {exc}"
                        ) from exc
                    if text is None or not text.strip():
                        continue
                    pages.append(
                        {
                            "source": path.name,
                            "page": page_number,
                            "text": text,
                        }
                    )
        except PDFLoadError:
            raise
        except PermissionError as exc:
            raise PDFLoadError(f"Permission denied reading PDF: {path}") from exc
        except Exception as exc:
            raise PDFLoadError(
                f"Failed to read PDF '{path.name}': it may be invalid, corrupted, "
                f"or encrypted ({type(exc).__name__}: {exc})"
            ) from exc

        return pages