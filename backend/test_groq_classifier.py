import sys
import os
import fitz  # PyMuPDF to create mock PDF and Image documents for tests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.document_context import prepare_classification_context
from app.services.groq_classifier import classify_document

def create_mock_pdf_bytes(text_lines: list) -> bytes:
    """Helper to generate in-memory visual PDF bytes for testing."""
    doc = fitz.open()
    page = doc.new_page(width=500, height=350)
    y = 40
    for line in text_lines:
        page.insert_text((40, y), line, fontsize=12)
        y += 25
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

def create_greeting_card_png_bytes() -> bytes:
    """Helper to generate a visual birthday card PNG image."""
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((50, 80), "HAPPY BIRTHDAY!", fontsize=22)
    page.insert_text((50, 130), "Wishing you a wonderful year ahead!", fontsize=14)
    page.insert_text((50, 170), "Best Wishes, Friends & Family", fontsize=12)
    pix = page.get_pixmap()
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes

def print_test_result(name: str, filename: str, file_type: str, subject: str, result, expected_rel: str, expected_type: str):
    print("=" * 50)
    print(f"TEST CASE: {name}")
    print("=" * 50)
    print("\nINPUT SUMMARY\n")
    print(f"Filename: {filename}")
    print(f"File Type: {file_type}")
    print(f"Email Subject: {subject} (Ignored by Vision Model)")
    
    print("\nCLASSIFICATION RESULT\n")
    print(f"Financial Relevance: {result.financial_relevance.value if hasattr(result.financial_relevance, 'value') else result.financial_relevance}")
    print(f"Document Type: {result.document_type.value if hasattr(result.document_type, 'value') else result.document_type}")
    print(f"Confidence: {result.confidence}")
    print(f"Reason: {result.reason}")
    
    print(f"\nEXPECTED RESULT:\nfinancial_relevance = {expected_rel}\ndocument_type = {expected_type}")
    
    rel_str = result.financial_relevance.value if hasattr(result.financial_relevance, 'value') else result.financial_relevance
    type_str = result.document_type.value if hasattr(result.document_type, 'value') else result.document_type
    
    status = "PASS" if rel_str == expected_rel and type_str == expected_type else "UNEXPECTED / FAIL"
    print(f"\nSTATUS:\n{status}\n")
    return status == "PASS"

def main():
    print("Starting Standalone Verification of Groq Vision AI Document Classifier...\n")
    
    results = []

    # CASE 1 — Indian GST Invoice (Visual PDF)
    c1_pdf = create_mock_pdf_bytes([
        "TAX INVOICE",
        "Invoice Number: INV-2026-1001",
        "Supplier: ABC Technologies Pvt Ltd",
        "GSTIN: 29ABCDE1234F1Z5",
        "Subtotal: Rs 50,000",
        "CGST: Rs 4,500 | SGST: Rs 4,500",
        "Total Amount: Rs 59,000"
    ])
    c1_att = {
        "filename": "invoice_1001.pdf",
        "mime_type": "application/pdf",
        "file_bytes": c1_pdf,
        "email_subject": "Invoice INV-2026-1001"
    }
    ctx1 = prepare_classification_context(c1_att)
    res1 = classify_document(ctx1)
    p1 = print_test_result("Indian GST Invoice (Visual PDF)", c1_att["filename"], c1_att["mime_type"], c1_att["email_subject"], res1, "FINANCIAL", "INVOICE")
    results.append(("Case 1 (Indian GST Invoice)", p1))

    # CASE 2 — Birthday Greeting Card (PNG Image) with Misleading Subject "Invoice INV-1000"
    c2_png = create_greeting_card_png_bytes()
    c2_att = {
        "filename": "invoice.pdf",  # Misleading filename
        "mime_type": "image/png",
        "file_bytes": c2_png,
        "email_subject": "Invoice INV-1000"  # Misleading email subject
    }
    ctx2 = prepare_classification_context(c2_att)
    res2 = classify_document(ctx2)
    p2 = print_test_result("Greeting Card Image (Misleading Subject & Filename)", c2_att["filename"], c2_att["mime_type"], c2_att["email_subject"], res2, "NOT_FINANCIAL", "GENERAL_DOCUMENT")
    results.append(("Case 2 (Greeting Card Image)", p2))

    # CASE 3 — Indian Purchase Order (Visual PDF) -> NOT_FINANCIAL per strict Sakshi Finance rule
    c3_pdf = create_mock_pdf_bytes([
        "PURCHASE ORDER",
        "PO Number: PO-2026-001",
        "Buyer: XYZ Corporation",
        "Supplier: ABC Technologies Pvt Ltd",
        "GSTIN: 29ABCDE1234F1Z5",
        "Item: Software License | Qty: 10",
        "Total Order Value: Rs 50,000"
    ])
    c3_att = {
        "filename": "PO_2026_001.pdf",
        "mime_type": "application/pdf",
        "file_bytes": c3_pdf,
        "email_subject": "Purchase Order PO-2026-001"
    }
    ctx3 = prepare_classification_context(c3_att)
    res3 = classify_document(ctx3)
    p3 = print_test_result("Indian Purchase Order (Visual PDF)", c3_att["filename"], c3_att["mime_type"], c3_att["email_subject"], res3, "NOT_FINANCIAL", "GENERAL_DOCUMENT")
    results.append(("Case 3 (Indian Purchase Order)", p3))

    # CASE 4 — Payment Receipt (Visual PDF) -> NOT_FINANCIAL per strict Sakshi Finance rule
    c4_pdf = create_mock_pdf_bytes([
        "PAYMENT RECEIPT",
        "Receipt Number: REC-45678",
        "Received From: ABC Corporation",
        "Payment Amount: Rs 25,000",
        "Payment Method: Bank Transfer",
        "Payment Status: PAID"
    ])
    c4_att = {
        "filename": "receipt_45678.pdf",
        "mime_type": "application/pdf",
        "file_bytes": c4_pdf,
        "email_subject": "Payment Receipt Confirmation"
    }
    ctx4 = prepare_classification_context(c4_att)
    res4 = classify_document(ctx4)
    p4 = print_test_result("Payment Receipt (Visual PDF)", c4_att["filename"], c4_att["mime_type"], c4_att["email_subject"], res4, "NOT_FINANCIAL", "GENERAL_DOCUMENT")
    results.append(("Case 4 (Payment Receipt)", p4))

    # CASE 5 — Blank Image Document
    blank_doc = fitz.open()
    blank_page = blank_doc.new_page(width=100, height=100)
    blank_bytes = blank_page.get_pixmap().tobytes("png")
    blank_doc.close()
    c5_att = {
        "filename": "blank_scan.png",
        "mime_type": "image/png",
        "file_bytes": blank_bytes,
        "email_subject": "Invoice Scan"
    }
    ctx5 = prepare_classification_context(c5_att)
    res5 = classify_document(ctx5)
    p5 = print_test_result("Blank Image Document", c5_att["filename"], c5_att["mime_type"], c5_att["email_subject"], res5, "UNKNOWN", "UNKNOWN")
    results.append(("Case 5 (Blank Image)", p5))

    print("=" * 50)
    print("SUMMARY OF GROQ VISION VERIFICATION RUN")
    print("=" * 50)
    for name, passed in results:
        print(f"{name}: {'PASS' if passed else 'FAIL'}")

if __name__ == "__main__":
    main()
