from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
import sys
import os
import subprocess
import pymupdf
import pytesseract
from PIL import Image
import io

MAX_OCR_PAGES = 30
_ocr_executor = ThreadPoolExecutor(max_workers=2)

# Prevent pytesseract from popping up console windows on Windows
if sys.platform == "win32":
    try:
        # Check if tesseract binary exists in PATH or standard locations
        has_tess = False
        for p in os.environ.get("PATH", "").split(os.pathsep):
            if (Path(p) / "tesseract.exe").exists():
                has_tess = True
                break
        if not has_tess and not Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe").exists():
            # Tesseract not installed, avoid unnecessary subprocess timeouts
            pass
    except Exception:
        pass

def perform_page_ocr(pixmap_bytes: bytes, lang: str = "por+eng") -> str:
    try:
        img = Image.open(io.BytesIO(pixmap_bytes))
        try:
            return pytesseract.image_to_string(img, lang=lang)
        except Exception:
            return pytesseract.image_to_string(img)
    except Exception as e:
        logger.debug("Page OCR failed: {}", e)
        return ""

def ocr_scanned_pdf(pdf_path: Path, max_pages: int = MAX_OCR_PAGES) -> str:
    """
    Renders PDF pages to images and runs OCR in parallel (pool <= 2).
    """
    try:
        doc = pymupdf.open(str(pdf_path))
        total_pages = min(len(doc), max_pages)
        if total_pages == 0:
            doc.close()
            return ""

        page_pixmaps = []
        for i in range(total_pages):
            page = doc[i]
            # Render at 150 DPI for fast and accurate OCR
            pix = page.get_pixmap(dpi=150)
            page_pixmaps.append(pix.tobytes("png"))

        doc.close()

        # Run OCR in pool
        results = list(_ocr_executor.map(perform_page_ocr, page_pixmaps))
        full_ocr_text = "\n".join([r.strip() for r in results if r.strip()])
        logger.info("OCR completed for {} ({} pages, {} chars)", pdf_path.name, total_pages, len(full_ocr_text))
        return full_ocr_text
    except Exception as e:
        logger.warning("OCR failed on {}: {}", pdf_path, e)
        return ""
