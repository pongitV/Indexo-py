from pathlib import Path
from typing import Dict, Any, Tuple
import pymupdf
from loguru import logger

def extract_pdf_text_and_meta(pdf_path: Path) -> Tuple[str, Dict[str, Any], bool]:
    """
    Extracts text, metadata and detects if PDF is scanned (image-only).
    Handles encrypted, password-protected, and corrupted files defensively.
    Returns (extracted_text, metadata_dict, is_scanned).
    """
    text_chunks = []
    meta: Dict[str, Any] = {}
    is_scanned = True
    doc = None

    try:
        doc = pymupdf.open(str(pdf_path))
        if doc.is_encrypted:
            # Try decrypting with empty password
            if not doc.authenticate(""):
                logger.debug("PDF is password-protected: {}", pdf_path)
                return "", {"encrypted": True}, False

        meta = doc.metadata or {}

        for page in doc:
            try:
                page_text = page.get_text("text")
                if page_text and page_text.strip():
                    text_chunks.append(page_text.strip())
                    is_scanned = False
            except Exception as page_err:
                logger.debug("Error extracting page in {}: {}", pdf_path, page_err)
                continue

    except Exception as e:
        logger.debug("Defensive fallback for unreadable PDF {}: {}", pdf_path, e)
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass

    full_text = "\n".join(text_chunks)
    return full_text, meta, is_scanned
