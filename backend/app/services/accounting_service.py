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
        self.base_url = (base_url or settings.COLAB_ACCOUNTING_API_URL).rstrip("/")
        self.timeout = timeout or settings.INFERENCE_TIMEOUT

    async def check_health(self) -> bool:
        """Check if Colab Qwen3-4B accounting endpoint is reachable and responsive."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(
                    f"{self.base_url}/health",
                    headers={"ngrok-skip-browser-warning": "1"},
                )
                return res.status_code == 200
        except Exception as e:
            logger.warning(f"Accounting Colab health check failed: {e}")
            return False

    async def categorize_accounting(
        self,
        invoice_json: Dict[str, Any],
        chart_of_accounts: Optional[List[Dict[str, Any]]] = None,
        available_taxes: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Sends complete extracted invoice JSON to Qwen3-4B for line-item accounting
        classification and TDS analysis.
        """
        if not isinstance(invoice_json, dict) or not invoice_json:
            raise ValueError("invoice_json must be a non-empty dictionary")

        coa = chart_of_accounts or DEFAULT_CHART_OF_ACCOUNTS
        taxes = available_taxes or DEFAULT_AVAILABLE_TAXES

        endpoint = f"{self.base_url}/api/infer/categorize-accounting"
        payload = {
            "invoice_json": invoice_json,
            "chart_of_accounts": coa,
            "available_taxes": taxes,
        }

        logger.info(
            f"Sending accounting categorization request to Colab Qwen3-4B ({endpoint}) with timeout={self.timeout}s"
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
                    f"Colab accounting API returned status {response.status_code}: {error_body}"
                )
                raise RuntimeError(
                    f"Colab accounting inference error (status {response.status_code}): {error_body}"
                )

            data = response.json()
            if not isinstance(data, dict):
                raise ValueError(
                    f"Malformed response from Colab accounting API: expected dict, got {type(data).__name__}"
                )

            # Ensure expected top-level keys are present or initialized
            if "accounting" not in data:
                data["accounting"] = []
            if "tds" not in data:
                data["tds"] = {}

            logger.info("Successfully received and validated Qwen3-4B accounting output.")
            return data

        except httpx.TimeoutException as exc:
            logger.error(
                f"Colab Qwen3-4B inference timed out after {self.timeout}s: {exc}"
            )
            raise TimeoutError(
                f"Accounting inference request timed out after {self.timeout} seconds on Colab."
            ) from exc

        except httpx.ConnectError as exc:
            logger.error(
                f"Failed to connect to Colab accounting server at {self.base_url}: {exc}"
            )
            raise RuntimeError(
                f"Colab accounting server at {self.base_url} is unreachable or offline."
            ) from exc

        except httpx.HTTPError as exc:
            logger.error(f"HTTP error communicating with Colab accounting server: {exc}")
            raise RuntimeError(f"HTTP communication error: {str(exc)}") from exc


accounting_service = AccountingService()
