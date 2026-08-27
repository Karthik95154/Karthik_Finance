import logging
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class SupabaseStorageService:
    def __init__(self):
        self.base_url = settings.SUPABASE_URL.rstrip("/")
        self.bucket = settings.SUPABASE_STORAGE_BUCKET
        self.service_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.headers = {
            "Authorization": f"Bearer {self.service_key}",
            "apikey": self.service_key,
        }

    async def upload_file(
        self,
        file_bytes: bytes,
        file_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Uploads raw binary bytes to the private Supabase Storage bucket."""
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{file_path}"
        headers = {
            **self.headers,
            "Content-Type": content_type,
            "x-upsert": "true",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, content=file_bytes)
            if response.status_code not in (200, 201):
                logger.error(
                    f"Supabase upload failed [{response.status_code}]: {response.text}"
                )
                raise RuntimeError(
                    f"Supabase storage upload failed: {response.text}"
                )
            return file_path

    async def download_file(self, file_path: str) -> bytes:
        """Downloads the unmodified binary from the private Supabase bucket."""
        url = f"{self.base_url}/storage/v1/object/authenticated/{self.bucket}/{file_path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self.headers)
            if response.status_code != 200:
                logger.error(
                    f"Supabase download failed [{response.status_code}]: {response.text}"
                )
                raise FileNotFoundError(
                    f"File '{file_path}' not found in storage or error: {response.text}"
                )
            return response.content

    async def delete_file(self, file_path: str) -> bool:
        """Deletes a file from the private bucket."""
        url = f"{self.base_url}/storage/v1/object/{self.bucket}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(
                "DELETE",
                url,
                headers=self.headers,
                json={"prefixes": [file_path]},
            )
            return response.status_code in (200, 204)

    async def check_health(self) -> bool:
        """Verifies bucket accessibility and authentication."""
        url = f"{self.base_url}/storage/v1/bucket/{self.bucket}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self.headers)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Storage health check error: {e}")
            return False


storage_service = SupabaseStorageService()
