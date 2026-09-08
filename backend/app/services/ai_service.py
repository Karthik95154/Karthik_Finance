import asyncio
import base64
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self, base_url: str = None):
        self.colab_url = (base_url or settings.kimi_k3_url).strip().rstrip("/")
        self.timeout = float(settings.INFERENCE_TIMEOUT)

    async def check_colab_health(self) -> bool:
        """Checks if the Kimi K3 Single Colab server is reachable."""
        detailed = await self.check_colab_health_detailed()
        return detailed.get("status") == "online"

    async def check_colab_health_detailed(self) -> Dict[str, Any]:
        """Checks if the Kimi K3 Single Colab server is reachable with exact status code and latency."""
        import time
        start_t = time.time()
        endpoint = f"{self.colab_url}/health"
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(
                    endpoint,
                    headers={"ngrok-skip-browser-warning": "1"},
                )
                latency = round((time.time() - start_t) * 1000, 1)
                if res.status_code == 200:
                    return {
                        "name": "Kimi K3 Single Colab Engine",
                        "status": "online",
                        "status_code": 200,
                        "message": "200 OK - Active & Responsive",
                        "latency_ms": latency,
                        "endpoint": self.colab_url,
                    }
                elif res.status_code == 404:
                    return {
                        "name": "Kimi K3 Single Colab Engine",
                        "status": "404_error",
                        "status_code": 404,
                        "message": "404 Not Found - Health endpoint missing on server",
                        "latency_ms": latency,
                        "endpoint": self.colab_url,
                    }
                else:
                    return {
                        "name": "Kimi K3 Single Colab Engine",
                        "status": f"{res.status_code}_error",
                        "status_code": res.status_code,
                        "message": f"HTTP {res.status_code} Error",
                        "latency_ms": latency,
                        "endpoint": self.colab_url,
                    }
        except httpx.ConnectError:
            return {
                "name": "Kimi K3 Single Colab Engine",
                "status": "offline",
                "status_code": None,
                "message": "Offline (Connection Refused / ngrok Tunnel Down)",
                "latency_ms": None,
                "endpoint": self.colab_url,
            }
        except httpx.TimeoutException:
            return {
                "name": "Kimi K3 Single Colab Engine",
                "status": "timeout",
                "status_code": None,
                "message": "Timeout (>4s) - Endpoint not responding",
                "latency_ms": None,
                "endpoint": self.colab_url,
            }
        except Exception as e:
            return {
                "name": "Kimi K3 Single Colab Engine",
                "status": "error",
                "status_code": None,
                "message": f"Error: {str(e)}",
                "latency_ms": None,
                "endpoint": self.colab_url,
            }

    async def extract_invoice_vlm(
        self,
        file_bytes: bytes,
        filename: str = "invoice.pdf",
        content_type: str = "application/pdf",
        chart_of_accounts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Calls Kimi K3 Single Colab service using Base64 JSON payload.

        Sends file Base64 image and authenticated user's active Zoho Chart of Accounts list.
        Uses generous configurable timeout (default 900s) to allow long-running inference.
        """
        if not file_bytes or len(file_bytes) == 0:
            raise ValueError("File content is empty.")

        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        magic_hex = file_bytes[:16].hex()
        logger.info(
            "VLM Request preparation | filename=%s content_type=%s size=%d sha256=%s magic=%s coa_count=%d",
            filename,
            content_type,
            len(file_bytes),
            sha256_hash,
            magic_hex,
            len(chart_of_accounts or []),
        )

        endpoint = f"{self.colab_url}/api/infer/k3-invoice"
        logger.info(f"Sending extraction request to Kimi K3 Colab ({endpoint}) with timeout={self.timeout}s")

        file_b64 = base64.b64encode(file_bytes).decode("utf-8")

        # ── TDS Analysis Instructions ─────────────────────────────────────────
        # Injected into Colab payload so the model uses current statutory rules.
        # The backend (tds_engine.py) always computes the final TDS amount —
        # the model MUST NOT calculate or return a tds_amount.
        TDS_INSTRUCTIONS = (
            "## TDS / Withholding Tax Analysis\n\n"
            "You are acting as a senior Indian chartered accountant.\n"
            "Apply the Income-tax Act, 1961 as amended up to the transaction/event date visible on this invoice.\n"
            "If the invoice date is on or after 01-Apr-2026, apply provisions of the Income-tax Act, 2025 "
            "(effective 01-Apr-2026) where they differ from the 1961 Act (e.g., updated thresholds, merged sections).\n\n"

            "### Your task — populate tds_support with EXACTLY these keys:\n\n"

            "1. **tds_applicable_candidate** (boolean | null)\n"
            "   - true  → the payment event described on this invoice is a prescribed TDS event under the applicable Act.\n"
            "   - false → the payment is genuinely outside all TDS provisions after threshold analysis.\n"
            "   - null  → insufficient information to determine (flag requires_backend_validation = true).\n"
            "   - Cloud/SaaS/IaaS/PaaS invoices where the purchaser is an Indian entity: treat as fees for "
            "technical services → tds_applicable_candidate = true unless a specific exemption applies.\n\n"

            "2. **payment_nature** (string)\n"
            "   Plain English description of what is being purchased, e.g.:\n"
            "   'Cloud compute and storage services (IaaS)' | 'Software subscription (SaaS)' | "
            "   'Professional consulting services' | 'Construction sub-contract' | 'Office rent'\n\n"

            "3. **provision_candidate** (string | null)\n"
            "   The exact section number and short title from the applicable Act, e.g.:\n"
            "   '194J – Fees for professional or technical services' | '194C – Payment to contractors' | "
            "   '194I – Rent' | '194H – Commission or brokerage' | '194Q – Purchase of goods'\n"
            "   Return null only if tds_applicable_candidate is false or null.\n"
            "   DO NOT default to '194J / 194C' as a combined fallback — choose the single most applicable section.\n\n"

            "4. **law_version_candidate** (string)\n"
            "   The Act version governing this invoice:\n"
            "   'Income-tax Act, 1961' or 'Income-tax Act, 2025' based on the invoice date.\n\n"

            "5. **rate_candidate** (number | null)\n"
            "   The statutory TDS rate (%) for the identified section and entity type.\n"
            "   Use the rate applicable on the invoice date.\n"
            "   Examples: 2.0 for 194C (company), 1.0 for 194C (individual/HUF), 10.0 for 194J professional, "
            "   2.0 for 194J technical, 10.0 for 194I, 5.0 for 194H, 0.1 for 194Q.\n"
            "   If vendor PAN is missing or invalid → rate_candidate = 20.0 (Section 206AA).\n"
            "   Return null only if tds_applicable_candidate is false or null.\n\n"

            "6. **base_candidate** (number | null)\n"
            "   The pre-tax amount (excluding GST) on which TDS is to be computed, as printed on the invoice.\n"
            "   This is the taxable value / subtotal BEFORE GST — never include GST in the TDS base.\n"
            "   Return null if the amount is not determinable from the document.\n\n"

            "7. **threshold_status** (string)\n"
            "   Whether the payment exceeds the annual threshold for the identified section:\n"
            "   'EXCEEDS_THRESHOLD' | 'BELOW_THRESHOLD' | 'CUMULATIVE_CHECK_REQUIRED' | 'NOT_APPLICABLE'\n"
            "   Use 'CUMULATIVE_CHECK_REQUIRED' when a single invoice looks below threshold but aggregate "
            "   vendor payments may cross it.\n\n"

            "8. **pan_status** (string)\n"
            "   'VALID_PAN_PROVIDED' | 'PAN_MISSING' | 'PAN_INVALID_FORMAT' | 'PANNOTAVBL'\n"
            "   Based on the vendor PAN visible on the document.\n\n"

            "9. **requires_backend_validation** (boolean)\n"
            "   Set true when cumulative vendor data (prior payments) is needed to confirm threshold breach.\n\n"

            "10. **reason** (string)\n"
            "    One or two sentences explaining your determination, citing the section and key facts.\n\n"

            "### STRICT RULES:\n"
            "- DO NOT output a tds_amount or calculated_tds_amount field — the backend engine computes the final amount.\n"
            "- DO NOT combine two sections in provision_candidate (e.g., '194J / 194C' is forbidden).\n"
            "- DO NOT fabricate a section. If genuinely uncertain between two sections, set "
            "  provision_candidate to the more likely one and set requires_backend_validation = true.\n"
            "- DO NOT apply TDS on the GST component — the base is always the pre-tax value.\n"
            "- Honour the invoice date for law version selection; do not assume current date.\n"
        )
        # ─────────────────────────────────────────────────────────────────────

        payload = {
            "image_base64": file_b64,
            "file_base64": file_b64,
            "filename": filename,
            "content_type": content_type,
            "chart_of_accounts": chart_of_accounts or [],
            "tds_instructions": TDS_INSTRUCTIONS,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "ngrok-skip-browser-warning": "1",
                    },
                )
            except httpx.ConnectError as e:
                logger.error(f"Failed to connect to Kimi K3 Colab at {self.colab_url}: {e}")
                raise RuntimeError(
                    f"Kimi K3 Colab server unreachable at {self.colab_url}. Please ensure the Colab notebook and ngrok tunnel are running."
                ) from e
            except httpx.TimeoutException as e:
                logger.error(f"Kimi K3 Colab inference request timed out after {self.timeout}s: {e}")
                raise TimeoutError(
                    f"Kimi K3 inference timed out after {int(self.timeout)}s. The Colab GPU server may be busy or experiencing high load."
                ) from e
            except Exception as e:
                logger.error(f"Unexpected error communicating with Kimi K3 Colab: {e}")
                raise RuntimeError(f"Colab communication error: {str(e)}") from e

            if response.status_code not in (200, 202):
                resp_text = response.text
                if "ERR_NGROK" in resp_text or "<!DOCTYPE html>" in resp_text or response.status_code == 404:
                    err_msg = (
                        f"Kimi K3 Colab GPU endpoint ({self.colab_url}) is offline or unreachable "
                        f"(Status {response.status_code}). Please start your Google Colab notebook and update KIMI_K3_SERVICE_URL in backend/.env."
                    )
                else:
                    err_msg = f"Kimi K3 extraction request failed [{response.status_code}]: {resp_text[:300]}"
                logger.error(err_msg)
                raise RuntimeError(err_msg)

            try:
                init_data = response.json()
            except Exception as e:
                logger.error(f"Failed to decode JSON from Colab response: {response.text[:300]}")
                raise ValueError(f"Malformed JSON returned from Kimi K3: {str(e)}") from e

            result = init_data

            # Handle Async Background Job Polling from Colab
            if isinstance(result, dict) and (
                result.get("status") in ("processing", "queued", "running")
                or "poll_endpoint" in result
                or ("job_id" in result and "data" not in result)
            ):
                job_id = result.get("job_id")
                poll_path = result.get("poll_endpoint") or (f"/api/infer/jobs/{job_id}" if job_id else None)
                if poll_path:
                    poll_url = f"{self.colab_url.rstrip('/')}/{poll_path.lstrip('/')}"
                    logger.info(f"Colab returned async job {job_id}. Polling {poll_url} until completion...")

                    start_time = asyncio.get_event_loop().time()
                    poll_interval = 4.0

                    while (asyncio.get_event_loop().time() - start_time) < self.timeout:
                        await asyncio.sleep(poll_interval)
                        try:
                            poll_res = await client.get(
                                poll_url,
                                headers={
                                    "Accept": "application/json",
                                    "ngrok-skip-browser-warning": "1",
                                },
                            )
                            if poll_res.status_code == 200:
                                job_data = poll_res.json()
                                job_status = job_data.get("status", "").lower()

                                if job_status in ("completed", "success", "done"):
                                    logger.info(f"Colab job {job_id} completed successfully!")
                                    # Return either the full payload or the inner result
                                    return job_data.get("result") or job_data.get("data") or job_data
                                elif job_status in ("failed", "error"):
                                    err_detail = job_data.get("error") or job_data.get("message") or "Unknown job error"
                                    logger.error(f"Colab job {job_id} failed: {err_detail}")
                                    raise RuntimeError(f"Kimi K3 inference job failed: {err_detail}")
                                else:
                                    logger.debug(f"Colab job {job_id} still {job_status}...")
                            elif poll_res.status_code in (404, 502, 503):
                                logger.warning(f"Polling job endpoint returned {poll_res.status_code}, retrying...")
                        except httpx.RequestError as exc:
                            logger.warning(f"Transient error polling Colab job {job_id}: {exc}")

                    raise TimeoutError(f"Colab job {job_id} did not finish within {self.timeout}s timeout.")

            return result


ai_service = AIService()
