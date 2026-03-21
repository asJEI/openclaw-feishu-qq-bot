import httpx
import logging

logger = logging.getLogger(__name__)

async def post_request(url, data=None, headers=None, json=None):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, data=data, headers=headers, json=json)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"HTTP Request Error: {e}")
            return None