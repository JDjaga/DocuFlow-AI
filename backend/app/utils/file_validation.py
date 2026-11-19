"""Validation rules for uploaded files (no extraction happening here).

WHAT THIS FILE DOES
    Rejects anything that is not an allowed, correctly sized, genuinely
    valid PDF/TXT file. Pure checks, no I/O side effects.

WHY IT EXISTS
    Uploaded files are untrusted. All checks live in one place so
    file_service.py can focus on reading text and routers stay small.

HOW IT CONNECTS
    services/file_service.py calls these functions before extracting text.
"""
from app.core.config import settings
from app.core.constants import ALLOWED_EXTENSIONS, FILE_SIGNATURES
from app.utils.errors import bad_request


def allowed_extensions() -> list[str]:
    """Public helper used by the health endpoint and the frontend docs."""
    return list(ALLOWED_EXTENSIONS)


def validate_size(size: int | None) -> None:
    """Reject files larger than MAX_FILE_SIZE_MB."""
    limit = settings.max_file_size_bytes
    if size is not None and size > limit:
        raise bad_request(
            f"File is too large ({size // (1024 * 1024)} MB). "
            f"Maximum allowed size is {settings.MAX_FILE_SIZE_MB} MB."
        )


def validate_extension(filename: str) -> str:
    """Return the lower-cased extension or raise 400."""
    name = (filename or "").strip()
    if not name:
        raise bad_request("No file was received. Please choose a PDF or TXT file.")

    extension = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(ALLOWED_EXTENSIONS)
        raise bad_request(f"Unsupported file type '{extension or 'unknown'}'. Allowed: {allowed}.")
    return extension


def validate_signature(extension: str, content: bytes) -> None:
    """Verify the real file content instead of trusting the file name.

    PDFs must start with the `%PDF` magic bytes. A file renamed to
    "report.pdf" that is actually something else is rejected here.
    """
    signatures = FILE_SIGNATURES.get(extension)
    if not signatures:
        return  # .txt has no required magic bytes
    if not any(content.startswith(signature) for signature in signatures):
        raise bad_request("This file does not look like a valid PDF (file signature mismatch).")


def validate_text_input(raw_text: str) -> str:
    """Validate text pasted directly into the browser textarea."""
    text = (raw_text or "").strip()
    if not text:
        raise bad_request("Paste some text or upload a file before analyzing.")
    if len(text) > settings.MAX_INPUT_CHARS:
        raise bad_request(
            f"Text is too long ({len(text)} characters). "
            f"Maximum allowed is {settings.MAX_INPUT_CHARS} characters."
        )
    return text
