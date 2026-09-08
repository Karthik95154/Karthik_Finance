import pytest

def detect_file_type(raw_bytes: bytes) -> str:
    """
    Detects file type using binary signatures / magic bytes.
    Returns: 'pdf', 'jpeg', 'png', 'webp', or 'unknown'.
    """
    if not raw_bytes or len(raw_bytes) == 0:
        return "unknown"

    if raw_bytes.startswith(b"%PDF-"):
        return "pdf"

    if len(raw_bytes) >= 3 and raw_bytes[:3] == b"\xff\xd8\xff":
        return "jpeg"

    if len(raw_bytes) >= 8 and raw_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"

    if len(raw_bytes) >= 12 and raw_bytes[:4] == b"RIFF" and raw_bytes[8:12] == b"WEBP":
        return "webp"

    return "unknown"


def test_pdf_magic_detection():
    pdf_bytes = b"%PDF-1.4 header and content"
    assert detect_file_type(pdf_bytes) == "pdf"


def test_jpeg_magic_detection():
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    assert detect_file_type(jpeg_bytes) == "jpeg"


def test_png_magic_detection():
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    assert detect_file_type(png_bytes) == "png"


def test_webp_magic_detection():
    webp_bytes = b"RIFF\x00\x00\x00\x00WEBPVP8 "
    assert detect_file_type(webp_bytes) == "webp"


def test_empty_and_unknown_bytes():
    assert detect_file_type(b"") == "unknown"
    assert detect_file_type(b"hello world random text") == "unknown"

