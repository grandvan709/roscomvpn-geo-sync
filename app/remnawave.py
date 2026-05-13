import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


_RETRYABLE = (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError)


class RemnawaveClient:
    def __init__(self, api_url: str, bearer_token: str, caddy_token: str | None = None, timeout: int = 30):
        self.api_url = api_url.rstrip("/")
        headers = {"Authorization": f"Bearer {bearer_token}"}
        if caddy_token:
            headers["X-Api-Key"] = caddy_token
        self.client = httpx.Client(headers=headers, timeout=timeout, follow_redirects=True)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10), retry=retry_if_exception_type(_RETRYABLE), reraise=True)
    def get_subscription_settings(self) -> dict:
        r = self.client.get(f"{self.api_url}/api/subscription-settings")
        r.raise_for_status()
        body = r.json()
        return body.get("response") if isinstance(body, dict) and "response" in body else body

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10), retry=retry_if_exception_type(_RETRYABLE), reraise=True)
    def patch_subscription_settings(self, payload: dict) -> dict:
        r = self.client.patch(f"{self.api_url}/api/subscription-settings", json=payload)
        r.raise_for_status()
        return r.json()
