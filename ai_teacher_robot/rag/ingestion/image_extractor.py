import os
from typing import List, Dict, Any
from loguru import logger

try:
    import fitz
    FITZ_AVAILABLE = True
except ImportError:
    fitz = None
    FITZ_AVAILABLE = False

class ImageExtractor:
    """Renders PDF pages to images or extracts embedded visual assets from pages."""
    def __init__(self) -> None:
        pass

    def render_page_to_png(self, pdf_path: str, page_number: int, dpi: int = 150) -> bytes:
        """Renders a specific page of the PDF to PNG bytes."""
        if not FITZ_AVAILABLE:
            raise ImportError("PyMuPDF is required to render page images.")
            
        doc = fitz.open(pdf_path)
        try:
            page = doc[page_number - 1]
            pix = page.get_pixmap(dpi=dpi)
            png_bytes = pix.tobytes("png")
            return png_bytes
        finally:
            doc.close()

    def extract_embedded_images(self, pdf_path: str, page_number: int) -> List[bytes]:
        """Extracts all embedded images inside the specified PDF page."""
        if not FITZ_AVAILABLE:
            raise ImportError("PyMuPDF is required to extract embedded images.")

        doc = fitz.open(pdf_path)
        extracted_images = []
        try:
            page = doc[page_number - 1]
            image_list = page.get_images(full=True)
            
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                extracted_images.append(image_bytes)
                
            logger.info(f"Extracted {len(extracted_images)} embedded images on page {page_number}.")
        except Exception as e:
            logger.error(f"Failed to extract images from page {page_number}: {e}")
        finally:
            doc.close()

        return extracted_images
