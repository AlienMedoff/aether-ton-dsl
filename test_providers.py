# test_providers.py (исправленная версия)
import pytest
from unittest.mock import AsyncMock, patch
from providers import ToncenterProvider

@pytest.mark.asyncio
async def test_toncenter_provider_success():
    # Setup
    provider = ToncenterProvider("https://toncenter.com/api/v2/jsonRPC", "test_key")
    
    # 1. Setup response mock
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"result": {"balance": 1000}, "id": 1, "jsonrpc": "2.0"})
    
    # 2. Setup context manager
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_response
    
    with patch("aiohttp.ClientSession.post", return_value=mock_cm) as mock_post:
        # Execution
        result = await provider.request("get_balance", {"address": "EQ..."})
        
        # Assertion
        assert result == {"balance": 1000}
        mock_post.assert_called_once()
        
        # Убрали проверку kwargs["headers"], так как они в сессии, а не в post
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["method"] == "get_balance"
