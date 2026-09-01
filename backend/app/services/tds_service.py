import logging
from typing import Any, Dict, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class TDSService:
    """
    Client for Qwen3-4B / Groq TDS Proposal API endpoint.
    Calls POST /api/infer/tds with normalized invoice_json.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        self.base_url = (base_url or settings.tds_service_url).strip().rstrip("/")
        self.timeout = float(timeout or settings.INFERENCE_TIMEOUT)

    async def check_health(self) -> bool:
        """Check if TDS endpoint is reachable."""
        detailed = await self.check_health_detailed()
        return detailed.get("status") == "online"

    async def check_health_detailed(self) -> Dict[str, Any]:
        """Check if TDS endpoint is reachable with exact latency and status."""
        import time
        if not self.base_url:
            return {
                "name": "Qwen3-4B TDS Engine",
                "status": "offline",
                "status_code": None,
                "message": "TDS Service URL not configured",
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
                        "name": "Qwen3-4B TDS Engine",
                        "status": "online",
                        "status_code": 200,
                        "message": "200 OK - Active & Responsive",
                        "latency_ms": latency,
                        "endpoint": self.base_url,
                    }
                elif res.status_code == 404:
                    return {
                        "name": "Qwen3-4B TDS Engine",
                        "status": "404_error",
                        "status_code": 404,
                        "message": "404 Not Found - Health endpoint missing on server",
                        "latency_ms": latency,
                        "endpoint": self.base_url,
                    }
                else:
                    return {
                        "name": "Qwen3-4B TDS Engine",
                        "status": f"{res.status_code}_error",
                        "status_code": res.status_code,
                        "message": f"HTTP {res.status_code} Error",
                        "latency_ms": latency,
                        "endpoint": self.base_url,
                    }
        except httpx.ConnectError:
            return {
                "name": "Qwen3-4B TDS Engine",
                "status": "offline",
                "status_code": None,
                "message": "Offline (Connection Refused / ngrok Tunnel Down)",
                "latency_ms": None,
                "endpoint": self.base_url,
            }
        except httpx.TimeoutException:
            return {
                "name": "Qwen3-4B TDS Engine",
                "status": "timeout",
                "status_code": None,
                "message": "Timeout (>4s) - Endpoint not responding",
                "latency_ms": None,
                "endpoint": self.base_url,
            }
        except Exception as e:
            return {
                "name": "Qwen3-4B TDS Engine",
                "status": "error",
                "status_code": None,
                "message": f"Error: {str(e)}",
                "latency_ms": None,
                "endpoint": self.base_url,
            }

    async def assess_tds(self, invoice_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends normalized invoice JSON to TDS inference endpoint (POST /api/infer/tds).
        Returns exact tds_assessment dictionary.
        Does NOT fabricate TDS if service is unavailable.
        """
        if not isinstance(invoice_json, dict) or not invoice_json:
            raise ValueError("invoice_json must be a non-empty dictionary")

        if not self.base_url:
            logger.warning("[TDS-QWEN] TDS Service URL not configured. Returning unassigned assessment.")
            return self._build_unavailable_response("TDS Service URL not configured")

        endpoint = f"{self.base_url}/api/infer/tds"
        payload = {"invoice_json": invoice_json}

        logger.info(f"[TDS-QWEN] request started to ({endpoint}) with timeout={self.timeout}s")

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
                logger.error(f"[TDS-QWEN] API returned status {response.status_code}: {error_body}")
                return self._build_unavailable_response(f"HTTP {response.status_code}: {error_body}")

            logger.info("[TDS-QWEN] response received")
            data = response.json()

            if not isinstance(data, dict):
                logger.error(f"[TDS-QWEN] Malformed response type: expected dict, got {type(data).__name__}")
                return self._build_unavailable_response(f"Malformed response type: {type(data).__name__}")

            tds_assessment = data.get("tds_assessment")
            if not isinstance(tds_assessment, dict):
                logger.error("[TDS-QWEN] Response missing 'tds_assessment' dictionary")
                return self._build_unavailable_response("Missing 'tds_assessment' dictionary in response")

            logger.info("[TDS-QWEN] proposal parsed successfully")
            return {"tds_assessment": tds_assessment}

        except httpx.TimeoutException as exc:
            logger.error(f"[TDS-QWEN] Inference timed out after {self.timeout}s: {exc}")
            return self._build_unavailable_response(f"Inference timed out after {self.timeout}s")
        except httpx.ConnectError as exc:
            logger.error(f"[TDS-QWEN] Failed to connect to server at {self.base_url}: {exc}")
            return self._build_unavailable_response(f"Connection refused at {self.base_url}")
        except Exception as exc:
            logger.error(f"[TDS-QWEN] Error communicating with TDS server: {exc}")
            return self._build_unavailable_response(str(exc))

    def _build_unavailable_response(self, error_reason: str) -> Dict[str, Any]:
        """Builds explicit review-required structure without fabricating values."""
        return {
            "tds_assessment": {
                "tds_applicable": None,
                "nature_of_payment": None,
                "tds_provision": None,
                "tds_section": None,
                "tds_rate": None,
                "tds_base_amount": None,
                "proposed_tds_amount": None,
                "tds_needs_review": True,
                "tds_reasoning": f"Qwen TDS service unavailable: {error_reason}",
            }
        }


tds_service = TDSService()
