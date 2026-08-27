import asyncio
import time
import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from httpx import AsyncClient, ASGITransport
from app.main import app


async def test_live_stage2():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Upload sample invoice
        invoice_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "sample_test_invoice.png"
        )
        print(f"1. Uploading {invoice_file}...")
        with open(invoice_file, "rb") as f:
            files = {"file": ("sample_test_invoice.png", f.read(), "image/png")}

        res = await client.post("/api/v1/invoices/upload", files=files)
        print("Upload response status:", res.status_code)
        assert res.status_code == 201, f"Upload failed: {res.text}"
        data = res.json()
        invoice_id = data["invoice_id"]
        print("Created Invoice ID:", invoice_id, "Initial Status:", data["status"])

        # 2. Poll status until completion or failure
        print("2. Polling status from backend (calling real Colab Qwen3-VL in background)...")
        start_time = time.time()
        while True:
            status_res = await client.get(f"/api/v1/invoices/{invoice_id}/status")
            status_data = status_res.json()
            curr_status = status_data.get("status")
            elapsed = int(time.time() - start_time)
            print(f"[{elapsed}s] Status: {curr_status}")

            if curr_status == "COMPLETED":
                print("-> Real Qwen3-VL extraction completed successfully!")
                break
            elif curr_status == "FAILED":
                print("-> Extraction FAILED with error:", status_data.get("error_message"))
                break

            await asyncio.sleep(5)

        # 3. Retrieve complete invoice details
        print("3. Fetching full invoice details...")
        inv_res = await client.get(f"/api/v1/invoices/{invoice_id}")
        inv_data = inv_res.json()
        raw_vlm = inv_data.get("raw_vlm_output") or {}
        extracted_data = raw_vlm.get("data") or {}

        print("=" * 60)
        print("=== REAL QWEN3-VL EXTRACTION RESULTS ===")
        print("=" * 60)
        print("Vendor Name   :", extracted_data.get("vendor_name"))
        print("Vendor GSTIN  :", extracted_data.get("vendor_gstin"))
        print("Vendor Address:", extracted_data.get("vendor_address"))
        print("Customer Name :", extracted_data.get("customer_name"))
        print("Customer GSTIN:", extracted_data.get("customer_gstin"))
        print("Invoice Number:", extracted_data.get("invoice_number"))
        print("Invoice Date  :", extracted_data.get("invoice_date"))
        print("Due Date      :", extracted_data.get("due_date"))
        print("Subtotal      :", extracted_data.get("subtotal"))
        print("Tax Total     :", extracted_data.get("tax_total"))
        print("Total Amount  :", extracted_data.get("total_amount"))
        print("Bank Details  :", extracted_data.get("bank_details"))
        print("Line Items Count:", len(extracted_data.get("line_items", [])))
        for i, item in enumerate(extracted_data.get("line_items", [])):
            print(
                f"  Item {i+1}: {item.get('description')} | HSN: {item.get('hsn_code')} | Qty: {item.get('quantity')} | Price: {item.get('unit_price')} | Total: {item.get('total')}"
            )
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_live_stage2())
