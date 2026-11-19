"""File reading / text extraction service.

WHAT THIS FILE DOES
    extract_text_from_upload() -> reads an uploaded PDF/TXT and returns plain text
    extract_text_from_string() -> validates raw text pasted by the user

WHY IT EXISTS
    Extraction is a unit of work with its own failure modes (corrupt PDF,
    image-only PDF, wrong encoding). Keeping it here lets the documents
    router stay a two-line wrapper.

HOW IT CONNECTS
    routers/documents.py (analyze endpoint)
        -> file_service.extract_text_from_*()
        -> utils/file_validation.py (all size/extension/signature checks)
        -> ai_service.analyze_text(text)
"""
import io

from fastapi import UploadFile

from app.core.config import settings
from app.utils.errors import AppError, bad_request
from app.utils.file_validation import (
    validate_extension,
    validate_signature,
    validate_size,
    validate_text_input,
)


def extract_text_from_upload(upload: UploadFile) -> tuple[str, str | None]:
    """Read an uploaded PDF/TXT file.

    Returns:
        (extracted_text, original_filename)
    """
    filename = (upload.filename or "").strip()
    extension = validate_extension(filename)

    content = upload.file.read()
    validate_size(len(content))
    validate_signature(extension, content)

    text = _extract_pdf_text(content) if extension == ".pdf" else _extract_txt_text(content)
    return text, filename


def extract_text_from_string(raw_text: str) -> tuple[str, None]:
    """Validate and return text pasted into the textarea."""
    return validate_text_input(raw_text), None


def _extract_pdf_text(content: bytes) -> str:
    """Extract text from a PDF.

    Primary engine: pdfplumber - it understands layout coordinates, so
    table rows/columns and multi-column pages stay readable.
    Fallback: pypdf for PDFs pdfplumber cannot parse.
    """
    text = _extract_with_pdfplumber(content)
    if text is None:
        text = _extract_with_pypdf(content)

    if not text:
        raise bad_request(
            "No readable text found in the PDF. Scanned or image-only PDFs are not supported yet."
        )
    if len(text) > settings.MAX_INPUT_CHARS:
        text = text[: settings.MAX_INPUT_CHARS]
    return text


def _extract_with_pdfplumber(content: bytes) -> str | None:
    """Layout-aware extraction. Returns None when pdfplumber cannot parse."""
    try:
        import pdfplumber
    except ImportError:  # pragma: no cover - pdfplumber is a hard dependency
        return None

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            if not pdf.pages:
                raise bad_request("The PDF contains no pages.")

            parts = []
            for page in pdf.pages:
                # extract_text() clusters words by coordinates, which keeps
                # table cells on their own lines far better than a raw
                # content-stream read.
                page_text = page.extract_text() or ""
                if page_text.strip():
                    parts.append(page_text.strip())
            return "\n\n".join(parts).strip() or None
    except AppError:
        raise  # our own validation error - pass it through unchanged
    except Exception:  # noqa: BLE001 - pdfplumber raises several error types
        return None  # let the pypdf fallback try


def _extract_with_pypdf(content: bytes) -> str:
    """Fallback extraction using pypdf."""
    from pypdf import PdfReader  # imported lazily: keeps startup fast

    try:
        reader = PdfReader(io.BytesIO(content))
        if not reader.pages:
            raise bad_request("The PDF contains no pages.")

        text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except AppError:
        raise  # our own validation error - pass it through unchanged
    except Exception as exc:  # noqa: BLE001 - pypdf raises several error types
        raise bad_request(
            "Could not read this PDF. It may be corrupted or password protected."
        ) from exc
    return text


def _extract_txt_text(content: bytes) -> str:
    """Decode a TXT file, tolerating the encodings Windows users commonly save."""
    text = None
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        raise bad_request("Could not decode this text file. Please save it as UTF-8.")

    text = text.strip()
    if not text:
        raise bad_request("The text file is empty.")
    if len(text) > settings.MAX_INPUT_CHARS:
        text = text[: settings.MAX_INPUT_CHARS]
    return text
