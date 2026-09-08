"""
End-to-End Pipeline Verification Script
Tests: Upload -> VLM Extraction -> Status Polling -> Result Verification
"""
import asyncio
import hashlib
import time
import httpx

API = "http://127.0.0.1:8000/api/v1"
TEST_FILE = r"C:\Users\neera\Documents\Sakshi_HITL_Test\sample_test_invoice.png"

# Dev auth credentials
DEV_EMAIL = "admin@sakshi.dev"
DEV_PASS = "admin123"


async def main():
    print("=" * 60)
    print("E2E PIPELINE TEST")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Authenticate
        print("\n[1] Authenticating...")
        auth_res = await client.post(f"{API}/auth/token", json={
            "email": DEV_EMAIL,
            "dev_role": "ADMIN",
            "dev_tenant_id": "default-tenant-001",
            "dev_name": "Admin User",
        })
        if auth_res.status_code != 200:
            # Try dev auth
            auth_res = await client.post(f"{API}/auth/dev-login", json={
                "email": DEV_EMAIL,
                "role": "ADMIN",
            })
        
        if auth_res.status_code != 200:
            print(f"  AUTH FAILED: {auth_res.status_code} {auth_res.text[:200]}")
            return
        
        token = auth_res.json().get("access_token") or auth_res.json().get("token")
        if not token:
            print(f"  No token in response: {auth_res.json()}")
            return
        print(f"  Authenticated! Token: {token[:20]}...")
        
        headers = {"Authorization": f"Bearer {token}"}

        # Step 2: Read test file & compute hash
        print("\n[2] Reading test file...")
        with open(TEST_FILE, "rb") as f:
            file_bytes = f.read()
        
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        print(f"  File size: {len(file_bytes)} bytes")
        print(f"  SHA256: {sha256}")
        print(f"  Magic bytes: {file_bytes[:16].hex()}")

        # Step 3: Upload
        print("\n[3] Uploading invoice...")
        upload_res = await client.post(
            f"{API}/invoices/upload",
            headers=headers,
            files={"file": ("test_e2e_invoice.png", file_bytes, "image/png")},
        )
        
        if upload_res.status_code not in (200, 201):
            print(f"  UPLOAD FAILED: {upload_res.status_code} {upload_res.text[:300]}")
            return
        
        upload_data = upload_res.json()
        invoice_id = upload_data.get("invoice_id")
        print(f"  Upload OK! Invoice ID: {invoice_id}")
        print(f"  Status: {upload_data.get('status')}")
        print(f"  File hash: {upload_data.get('file_hash')}")

        # Step 4: Poll status until completion or failure
        print("\n[4] Polling extraction status...")
        start_time = time.time()
        max_wait = 300  # 5 minutes
        poll_interval = 3

        while (time.time() - start_time) < max_wait:
            await asyncio.sleep(poll_interval)
            
            status_res = await client.get(
                f"{API}/invoices/{invoice_id}/status",
                headers=headers,
            )
            
            if status_res.status_code != 200:
                print(f"  Poll error: {status_res.status_code} {status_res.text[:200]}")
                continue
            
            status_data = status_res.json()
            elapsed = round(time.time() - start_time, 1)
            current_status = status_data.get("status")
            acct_status = status_data.get("accounting_status")
            error = status_data.get("error_message")
            
            print(f"  [{elapsed}s] status={current_status} acct={acct_status} error={error}")

            if current_status == "FAILED":
                print(f"\n  EXTRACTION FAILED: {error}")
                break
            elif current_status in ("HITL_REVIEW", "FINAL_HITL_REVIEW", "APPROVED", "COMPLETED"):
                print(f"\n  EXTRACTION COMPLETE! Status: {current_status}")
                
                # Step 5: Verify extracted data
                print("\n[5] Verifying extracted data...")
                detail_res = await client.get(
                    f"{API}/invoices/{invoice_id}",
                    headers=headers,
                )
                
                if detail_res.status_code == 200:
                    inv = detail_res.json()
                    raw = inv.get("raw_vlm_output")
                    has_raw = raw is not None and raw != {}
                    print(f"  Has raw_vlm_output: {has_raw}")
                    
                    if has_raw:
                        data = raw.get("data") if isinstance(raw, dict) and "data" in raw else raw
                        if isinstance(data, dict):
                            print(f"  Keys: {list(data.keys())[:15]}")
                            print(f"  Vendor: {data.get('vendor_name')}")
                            print(f"  Invoice #: {data.get('invoice_number')}")
                            print(f"  Date: {data.get('invoice_date')}")
                            print(f"  Total: {data.get('total_amount')}")
                            items = data.get("line_items") or []
                            print(f"  Line items: {len(items)}")
                        else:
                            print(f"  raw type: {type(data)}")
                    
                    current = inv.get("current_vlm_output")
                    print(f"  Has current_vlm_output: {current is not None and current != {}}")
                else:
                    print(f"  Detail fetch failed: {detail_res.status_code}")
                
                break
        else:
            print(f"\n  TIMEOUT after {max_wait}s!")

    print("\n" + "=" * 60)
    print("E2E TEST COMPLETE")
    print("=" * 60)

asyncio.run(main())
