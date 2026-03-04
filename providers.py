# providers.py
import abc
import aiohttp
import logging
import asyncio

logger = logging.getLogger(__name__)

class BaseProvider(abc.ABC):
    """Abstract base for all network providers."""
    @abc.abstractmethod
    async def request(self, method: str, params: dict) -> dict:
        pass

class ToncenterProvider(BaseProvider):
    """Concrete provider for Toncenter API."""
    def __init__(self, api_url: str, api_key: str = None):
        self.api_url = api_url
        self.headers = {"X-API-Key": api_key} if api_key else {}
        self.timeout = aiohttp.ClientTimeout(total=10)

    async def request(self, method: str, params: dict) -> dict:
        async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as session:
            payload = {
                "method": method,
                "params": params,
                "id": 1,
                "jsonrpc": "2.0"
            }
            async with session.post(self.api_url, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Toncenter error {resp.status}: {text}")
                    raise Exception(f"Toncenter provider failure: {resp.status}")
                
                response = await resp.json()
                if "error" in response:
                    raise Exception(f"RPC error: {response['error']}")
                
                return response.get("result", {})
