import base64
import logging
from typing import Any, Dict
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        self.colab_url = settings.COLAB_API_URL.rstrip("/")
        self.timeout = float(settings.INFERENCE_TIMEOUT)

    async def check_colab_health(self) -> bool:
        """Checks if the Colab / ngrok Qwen3-VL server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(
                    f"{self.colab_url}/health",
                    headers={"ngrok-skip-browser-warning": "1"},
                )
                return res.status_code == 200
        except Exception as e:
            logger.warning(f"Colab health check failed: {e}")
            return False

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
                logger.error(f"Colab Qwen3-VL returned error [{response.status_code}]: {response.text}")
                raise RuntimeError(
                    f"Qwen3-VL extraction failed [{response.status_code}]: {response.text}"
                )

            try:
                result = response.json()
            except Exception as e:
                logger.error(f"Failed to decode JSON from Colab response: {response.text}")
                raise ValueError(f"Malformed JSON returned from Qwen3-VL: {str(e)}") from e

            return result


ai_service = AIService()
