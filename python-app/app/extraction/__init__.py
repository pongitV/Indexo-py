"""
Document and Text Extraction Module (PDF, DOCX, OCR).
"""

from app.extraction.pdf_extractor import extract_pdf_text_and_meta
from app.extraction.doc_extractor import extract_document_text, extract_docx_text, extract_odt_text
from app.extraction.ocr_engine import perform_page_ocr, ocr_scanned_pdf

__all__ = [
    "extract_pdf_text_and_meta",
    "extract_document_text",
    "extract_docx_text",
    "extract_odt_text",
    "perform_page_ocr",
    "ocr_scanned_pdf",
]
