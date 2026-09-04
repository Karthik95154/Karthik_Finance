import os
import pathlib
import logging
import time
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

LOCAL_STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage"))


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
        """Uploads raw binary bytes to local cache and Supabase Storage bucket."""
        # 1. Save to local disk cache immediately for fast & offline viewer rendering
        try:
            local_target = os.path.join(LOCAL_STORAGE_DIR, file_path)
            os.makedirs(os.path.dirname(local_target), exist_ok=True)
            with open(local_target, "wb") as f:
                f.write(file_bytes)
        except Exception as disk_err:
            logger.warning(f"Failed to write local storage cache: {disk_err}")

        # 2. Sync to Supabase Storage
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{file_path}"
        headers = {
            **self.headers,
            "Content-Type": content_type,
            "x-upsert": "true",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, headers=headers, content=file_bytes)
                if response.status_code not in (200, 201):
                    logger.warning(f"Supabase upload non-200 [{response.status_code}]: {response.text}")
        except Exception as e:
            logger.warning(f"Supabase cloud upload error (local copy preserved): {e}")

        return file_path

    async def download_file(self, file_path: str) -> bytes:
        """Downloads the unmodified binary from local cache, falling back to Supabase."""
        # 1. Check local cache first for instant retrieval
        local_target = os.path.join(LOCAL_STORAGE_DIR, file_path)
        if os.path.exists(local_target):
            try:
                with open(local_target, "rb") as f:
                    return f.read()
            except Exception as disk_err:
                logger.warning(f"Error reading local file copy: {disk_err}")

        # 2. Fallback to Supabase remote bucket
        url = f"{self.base_url}/storage/v1/object/authenticated/{self.bucket}/{file_path}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    # Cache locally for future requests
                    try:
                        os.makedirs(os.path.dirname(local_target), exist_ok=True)
                        with open(local_target, "wb") as f:
                            f.write(response.content)
                    except Exception:
                        pass
                    return response.content
                else:
                    logger.error(f"Supabase download failed [{response.status_code}]: {response.text}")
                    raise FileNotFoundError(f"File '{file_path}' not found in storage: {response.text}")
        except Exception as exc:
            if os.path.exists(local_target):
                with open(local_target, "rb") as f:
                    return f.read()
            raise FileNotFoundError(f"File '{file_path}' unreachable: {exc}")

    async def delete_file(self, file_path: str) -> bool:
        """Deletes a file from local cache and private bucket."""
        local_target = os.path.join(LOCAL_STORAGE_DIR, file_path)
        if os.path.exists(local_target):
            try:
                os.remove(local_target)
            except Exception:
                pass
        url = f"{self.base_url}/storage/v1/object/{self.bucket}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(
                "DELETE",
                url,
                headers=self.headers,
                json={"prefixes": [file_path]},
            )
            return response.status_code in (200, 204)

    _last_health_check_time: float = 0
    _last_health_status: bool = False

    async def check_health(self) -> bool:
        """Verifies bucket accessibility and authentication with a 60-second cache."""
        now = time.time()
        if (now - self._last_health_check_time) < 60.0:
            return self._last_health_status

        url = f"{self.base_url}/storage/v1/bucket/{self.bucket}"
        try:
            timeout_config = httpx.Timeout(8.0, connect=4.0)
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                response = await client.get(url, headers=self.headers)
                self._last_health_status = response.status_code == 200
                self._last_health_check_time = now
                return self._last_health_status
        except Exception as e:
            err_desc = str(e).strip() or type(e).__name__
            logger.debug(f"Storage health check advisory: {err_desc}")
            self._last_health_status = False
            self._last_health_check_time = now
            return False


storage_service = SupabaseStorageService()
