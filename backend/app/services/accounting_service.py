import logging
import httpx
from typing import Dict, Any, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# Standard Default Chart of Accounts as fallback
DEFAULT_CHART_OF_ACCOUNTS: List[Dict[str, Any]] = [
    {"account_id": "ACC_1", "account_name": "Cloud Hosting & Infrastructure", "account_type": "expense"},
    {"account_id": "ACC_2", "account_name": "Software & Subscription Expenses", "account_type": "expense"},
    {"account_id": "ACC_3", "account_name": "Office Supplies & Stationery", "account_type": "expense"},
    {"account_id": "ACC_4", "account_name": "Professional & Legal Fees", "account_type": "expense"},
    {"account_id": "ACC_5", "account_name": "Consulting & Technical Services", "account_type": "expense"},
    {"account_id": "ACC_6", "account_name": "Hardware & Equipment", "account_type": "asset"},
    {"account_id": "ACC_7", "account_name": "Advertising & Marketing", "account_type": "expense"},
    {"account_id": "ACC_8", "account_name": "Travel & Conveyance", "account_type": "expense"},
    {"account_id": "ACC_9", "account_name": "Rent & Facility Expenses", "account_type": "expense"},
    {"account_id": "ACC_10", "account_name": "Telecommunications & Internet", "account_type": "expense"},
    {"account_id": "ACC_11", "account_name": "Utilities & Maintenance", "account_type": "expense"},
    {"account_id": "ACC_12", "account_name": "Shipping & Freight Charges", "account_type": "expense"},
]

# Standard Default Tax Records as fallback
DEFAULT_AVAILABLE_TAXES: List[Dict[str, Any]] = [
    {"tax_id": "TAX_0", "tax_name": "GST 0%", "tax_rate": 0.0, "tax_type": "GST"},
    {"tax_id": "TAX_5", "tax_name": "GST 5%", "tax_rate": 5.0, "tax_type": "GST"},
    {"tax_id": "TAX_12", "tax_name": "GST 12%", "tax_rate": 12.0, "tax_type": "GST"},
    {"tax_id": "TAX_18", "tax_name": "GST 18%", "tax_rate": 18.0, "tax_type": "GST"},
    {"tax_id": "TAX_28", "tax_name": "GST 28%", "tax_rate": 28.0, "tax_type": "GST"},
]


class AccountingService:
    """Client for Qwen3-4B Accounting & Tax Reasoning endpoint in Google Colab."""

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        self.base_url = (base_url or settings.coa_service_url).strip().rstrip("/")
        self.timeout = float(timeout or settings.INFERENCE_TIMEOUT)

    async def check_health(self) -> bool:
        """Check if Colab Qwen3-4B accounting endpoint is reachable and responsive."""
        detailed = await self.check_health_detailed()
        return detailed.get("status") == "online"

    async def check_health_detailed(self) -> Dict[str, Any]:
        """Check if Colab Qwen3-4B accounting endpoint is reachable with exact status code and latency."""
        import time
        if not self.base_url:
            return {
                "name": "Qwen3-4B Accounting Engine",
                "status": "offline",
                "status_code": None,
                "message": "COA Service URL not configured",
                "latency_ms": None,
                "endpoint": "",
            }

        start_t = time.time()
        endpoint = f"{self.base_url}/health"
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(
                    endpoint,
                    headers={"ngrok-skip-browser-warning": "1"},
                )
                latency = round((time.time() - start_t) * 1000, 1)
                if res.status_code == 200:
                    return {
                        "name": "Qwen3-4B Accounting Engine",
                        "status": "online",
                        "status_code": 200,
                        "message": "200 OK - Active & Responsive",
                        "latency_ms": latency,
                        "endpoint": self.base_url,
                    }
                elif res.status_code == 404:
                    return {
                        "name": "Qwen3-4B Accounting Engine",
                        "status": "404_error",
                        "status_code": 404,
                        "message": "404 Not Found - Health endpoint missing on server",
                        "latency_ms": latency,
                        "endpoint": self.base_url,
                    }
                else:
                    return {
                        "name": "Qwen3-4B Accounting Engine",
                        "status": f"{res.status_code}_error",
                        "status_code": res.status_code,
                        "message": f"HTTP {res.status_code} Error",
                        "latency_ms": latency,
                        "endpoint": self.base_url,
                    }
        except httpx.ConnectError:
            return {
                "name": "Qwen3-4B Accounting Engine",
                "status": "offline",
                "status_code": None,
                "message": "Offline (Connection Refused / ngrok Tunnel Down)",
                "latency_ms": None,
                "endpoint": self.base_url,
            }
        except httpx.TimeoutException:
            return {
                "name": "Qwen3-4B Accounting Engine",
                "status": "timeout",
                "status_code": None,
                "message": "Timeout (>4s) - Endpoint not responding",
                "latency_ms": None,
                "endpoint": self.base_url,
            }
        except Exception as e:
            return {
                "name": "Qwen3-4B Accounting Engine",
                "status": "error",
                "status_code": None,
                "message": f"Error: {str(e)}",
                "latency_ms": None,
                "endpoint": self.base_url,
            }

    async def categorize_accounting(
        self,
        invoice_json: Dict[str, Any],
        chart_of_accounts: Optional[List[Dict[str, Any]]] = None,
        available_taxes: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Sends complete extracted invoice JSON to Qwen3-4B for line-item accounting
        classification.
        """
        if not isinstance(invoice_json, dict) or not invoice_json:
            raise ValueError("invoice_json must be a non-empty dictionary")

        if not self.base_url:
            logger.warning("[COA-QWEN] COA Service URL not configured. Returning unassigned review lines.")
            return self._build_unavailable_response(invoice_json, "COA Service URL not configured")

        coa = chart_of_accounts if chart_of_accounts is not None else []
        taxes = available_taxes if available_taxes is not None else []

        endpoint = f"{self.base_url}/api/infer/categorize-accounting"
        payload = {
            "invoice_json": invoice_json,
            "chart_of_accounts": coa,
            "available_taxes": taxes,
        }

        logger.info(
            f"[COA-QWEN] request started to ({endpoint}) with timeout={self.timeout}s"
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "ngrok-skip-browser-warning": "1",
                    },
                )

            if response.status_code != 200:
                error_body = response.text[:500]
                logger.error(
                    f"[COA-QWEN] API returned status {response.status_code}: {error_body}"
                )
                return self._build_unavailable_response(invoice_json, f"HTTP {response.status_code}: {error_body}")

            logger.info("[COA-QWEN] response received")
            data = response.json()
            if not isinstance(data, dict):
                logger.error(f"[COA-QWEN] Malformed response type: expected dict, got {type(data).__name__}")
                return self._build_unavailable_response(invoice_json, f"Malformed response type: {type(data).__name__}")

            # Ensure expected accounting list is present
            raw_accounting = data.get("accounting")
            if not isinstance(raw_accounting, list):
                logger.error("[COA-QWEN] Response missing 'accounting' list")
                return self._build_unavailable_response(invoice_json, "Missing 'accounting' list in response")

            logger.info("[COA-QWEN] accounting parsed successfully")
            return {"accounting": raw_accounting}

        except httpx.TimeoutException as exc:
            logger.error(
                f"[COA-QWEN] Inference timed out after {self.timeout}s: {exc}"
            )
            return self._build_unavailable_response(invoice_json, f"Inference timed out after {self.timeout}s")

        except httpx.ConnectError as exc:
            logger.error(
                f"[COA-QWEN] Failed to connect to server at {self.base_url}: {exc}"
            )
            return self._build_unavailable_response(invoice_json, f"Connection refused at {self.base_url}")

        except Exception as exc:
            logger.error(f"[COA-QWEN] Error communicating with COA server: {exc}")
            return self._build_unavailable_response(invoice_json, str(exc))

    def _build_unavailable_response(self, invoice_json: Dict[str, Any], error_reason: str) -> Dict[str, Any]:
        """
        Builds explicit review-required records without fabricating account_id or account_name.
        """
        line_items = invoice_json.get("line_items") or []
        fallback = []
        if line_items:
            for pos, item in enumerate(line_items, 1):
                item_dict = item if isinstance(item, dict) else {}
                desc = item_dict.get("description") or f"Line {pos}"
                fallback.append({
                    "line_index": pos,
                    "source_description": desc,
                    "account_id": None,
                    "account_name": None,
                    "confidence_score": 0.0,
                    "ai_needs_review": True,
                    "accounting_reason": f"COA service unavailable: {error_reason}",
                })
        else:
            fallback.append({
                "line_index": 1,
                "source_description": invoice_json.get("vendor_name") or "Invoice Expense",
                "account_id": None,
                "account_name": None,
                "confidence_score": 0.0,
                "ai_needs_review": True,
                "accounting_reason": f"COA service unavailable: {error_reason}",
            })
        return {"accounting": fallback}


accounting_service = AccountingService()
