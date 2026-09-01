import base64
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Maximum number of PDF pages to render to comply with Groq API limit (max 3 images per request)
MAX_PDF_PAGES_TO_RENDER = 3


def extract_visual_page_images(file_bytes: bytes, mime_type: str) -> List[str]:
    """
    Extracts Base64 image data URLs (data:image/png;base64,...) from an attachment.
    - For PDFs: Renders up to MAX_PDF_PAGES_TO_RENDER pages as PNG images.
    - For Images (PNG, JPG, JPEG, TIF): Converts raw bytes directly into a Base64 image data URL.
    Returns a list of image data URLs.
    """
    image_urls = []
    if not file_bytes:
        return image_urls

    mime_clean = (mime_type or "").lower().strip()

    if mime_clean == "application/pdf" or mime_clean.endswith("pdf"):
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            pages_to_process = min(len(doc), MAX_PDF_PAGES_TO_RENDER)
            
            for page_index in range(pages_to_process):
                page = doc[page_index]
                # Render page at 150 DPI for good visual balance
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                b64_str = base64.b64encode(img_bytes).decode("utf-8")
                image_urls.append(f"data:image/png;base64,{b64_str}")
                
            doc.close()
        except ImportError:
            logger.error("PyMuPDF (fitz) is not installed. PDF page rendering failed.")
        except Exception as e:
            logger.warning(f"Failed to render PDF pages into images: {e}")
            
    elif any(img_type in mime_clean for img_type in ("image/", "png", "jpg", "jpeg", "tif", "tiff")):
        try:
            b64_str = base64.b64encode(file_bytes).decode("utf-8")
            fmt = "png"
            if "jpeg" in mime_clean or "jpg" in mime_clean:
                fmt = "jpeg"
            image_urls.append(f"data:image/{fmt};base64,{b64_str}")
        except Exception as e:
            logger.warning(f"Failed to format image bytes as Base64 data URL: {e}")
            
    return image_urls

def prepare_classification_context(attachment_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepares visual classification context.
    Strictly excludes external metadata (subject, body, filename) to eliminate bias.
    """
    file_bytes = attachment_data.get("file_bytes", b"")
    mime_type = attachment_data.get("mime_type", "")

    image_urls = extract_visual_page_images(file_bytes, mime_type)

    return {
        "image_urls": image_urls
    }
