import os
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

try:
    import fitz
    FITZ_AVAILABLE = True
except ImportError:
    fitz = None
    FITZ_AVAILABLE = False

try:
    import easyocr
    import numpy as np
    from PIL import Image
    import io
    EASYOCR_AVAILABLE = True
except ImportError:
    easyocr = None
    EASYOCR_AVAILABLE = False

class PDFLoader:
    """Extracts text page-by-page from PDFs using PyMuPDF, with EasyOCR fallback for scanned pages."""
    def __init__(self) -> None:
        self.ocr_reader = None

    def _init_ocr(self):
        if self.ocr_reader is None and EASYOCR_AVAILABLE:
            try:
                logger.info("Initializing EasyOCR reader...")
                self.ocr_reader = easyocr.Reader(['en'])
            except Exception as e:
                logger.warning(f"Failed to initialize EasyOCR: {e}")
                self.ocr_reader = None

    def load_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Synchronously loads PDF and extracts text per page."""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        path_obj = Path(pdf_path)
        pages = []

        if not FITZ_AVAILABLE:
            logger.error("PyMuPDF (fitz) is not available. Extraction cannot proceed.")
            raise ImportError("PyMuPDF is required for PDF text extraction.")

        doc = fitz.open(str(path_obj))
        try:
            for idx in range(doc.page_count):
                page = doc[idx]
                text = page.get_text()
                
                # Check if page is empty/scanned and OCR is available
                if not text.strip():
                    logger.info(f"Page {idx + 1} appears to be scanned or empty. Attempting OCR...")
                    ocr_text = self._ocr_page(page)
                    if ocr_text:
                        text = ocr_text
                
                pages.append({
                    "page_number": idx + 1,
                    "plain_text": text
                })
            logger.info(f"Successfully loaded PDF: {path_obj.name} ({len(pages)} pages)")
        finally:
            doc.close()

        return pages

    def _ocr_page(self, page: Any) -> str:
        """Renders page as image and runs EasyOCR on it."""
        self._init_ocr()
        if not self.ocr_reader:
            logger.warning("EasyOCR is not available or failed to initialize. Skipping OCR fallback.")
            return ""

        try:
            # Render page to low-res pixmap for OCR
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            
            # Read with PIL
            img = Image.open(io.BytesIO(img_bytes))
            # Convert to numpy array for EasyOCR
            img_np = np.array(img)
            
            results = self.ocr_reader.readtext(img_np, detail=0)
            ocr_text = "\n".join(results)
            logger.info(f"OCR successfully extracted {len(ocr_text)} characters.")
            return ocr_text
        except Exception as e:
            logger.error(f"Error during OCR of page: {e}")
            return ""
