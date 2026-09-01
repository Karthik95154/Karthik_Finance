import base64
import logging
from typing import Any, Dict
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self, base_url: str = None):
        self.colab_url = (base_url or settings.vl_service_url).strip().rstrip("/")
        self.timeout = float(settings.INFERENCE_TIMEOUT)

    async def check_colab_health(self) -> bool:
        """Checks if the Colab / ngrok Qwen3-VL server is reachable."""
        detailed = await self.check_colab_health_detailed()
        return detailed.get("status") == "online"

    async def check_colab_health_detailed(self) -> Dict[str, Any]:
        """Checks if the Colab / ngrok Qwen3-VL server is reachable with exact status code and latency."""
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
                        "name": "Qwen3-VL Vision Engine",
                        "status": "online",
                        "status_code": 200,
                        "message": "200 OK - Active & Responsive",
                        "latency_ms": latency,
                        "endpoint": self.colab_url,
                    }
                elif res.status_code == 404:
                    return {
                        "name": "Qwen3-VL Vision Engine",
                        "status": "404_error",
                        "status_code": 404,
                        "message": "404 Not Found - Health endpoint missing on server",
                        "latency_ms": latency,
                        "endpoint": self.colab_url,
                    }
                else:
                    return {
                        "name": "Qwen3-VL Vision Engine",
                        "status": f"{res.status_code}_error",
                        "status_code": res.status_code,
                        "message": f"HTTP {res.status_code} Error",
                        "latency_ms": latency,
                        "endpoint": self.colab_url,
                    }
        except httpx.ConnectError:
            return {
                "name": "Qwen3-VL Vision Engine",
                "status": "offline",
                "status_code": None,
                "message": "Offline (Connection Refused / ngrok Tunnel Down)",
                "latency_ms": None,
                "endpoint": self.colab_url,
            }
        except httpx.TimeoutException:
            return {
                "name": "Qwen3-VL Vision Engine",
                "status": "timeout",
                "status_code": None,
                "message": "Timeout (>4s) - Endpoint not responding",
                "latency_ms": None,
                "endpoint": self.colab_url,
            }
        except Exception as e:
            return {
                "name": "Qwen3-VL Vision Engine",
                "status": "error",
                "status_code": None,
                "message": f"Error: {str(e)}",
                "latency_ms": None,
                "endpoint": self.colab_url,
            }

    async def extract_invoice_vlm(self, file_bytes: bytes) -> Dict[str, Any]:
        """Calls Qwen3-VL on Colab with the Base64-encoded PDF/Image.
        
        Uses generous configurable timeout (default 900s) to allow long-running inference.
        """
        if not file_bytes:
            raise ValueError("File content is empty.")

        image_base64 = base64.b64encode(file_bytes).decode("utf-8")
        payload = {"image_base64": image_base64}
        endpoint = f"{self.colab_url}/api/infer/extract-invoice"

        logger.info(f"Sending extraction request to Colab Qwen3-VL ({endpoint}) with timeout={self.timeout}s")

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
                logger.error(f"Failed to connect to Colab Qwen3-VL at {self.colab_url}: {e}")
                raise RuntimeError(
                    f"Colab Qwen3-VL server unreachable at {self.colab_url}. Please ensure the Colab notebook and ngrok tunnel are running."
                ) from e
            except httpx.TimeoutException as e:
                logger.error(f"Colab Qwen3-VL request timed out after {self.timeout}s: {e}")
                raise TimeoutError(
                    f"Inference timed out after {int(self.timeout)}s. The model may be under heavy load."
                ) from e
            except Exception as e:
                logger.error(f"Unexpected error communicating with Colab Qwen3-VL: {e}")
                raise RuntimeError(f"Colab communication error: {str(e)}") from e

            if response.status_code != 200:
                resp_text = response.text
                if "ERR_NGROK" in resp_text or "<!DOCTYPE html>" in resp_text or response.status_code == 404:
                    err_msg = (
                        f"Colab Qwen3-VL GPU endpoint ({self.colab_url}) is offline or unreachable "
                        f"(Status {response.status_code}). Please start your Google Colab notebook and update COLAB_API_URL in backend/.env."
                    )
                else:
                    err_msg = f"Qwen3-VL extraction failed [{response.status_code}]: {resp_text[:300]}"
                logger.error(err_msg)
                raise RuntimeError(err_msg)

            try:
                result = response.json()
            except Exception as e:
                logger.error(f"Failed to decode JSON from Colab response: {response.text[:300]}")
                raise ValueError(f"Malformed JSON returned from Qwen3-VL: {str(e)}") from e

            return result


ai_service = AIService()
