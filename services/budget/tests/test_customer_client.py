import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.services.customer_client import get_customer
from shared.security.internal_service import INTERNAL_SERVICE_HEADER


@pytest.mark.anyio
async def test_get_customer_sends_internal_service_header(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKEN", "shared-secret")
    customer_id = uuid.uuid4()
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": str(customer_id), "name": "Test NGO"}]

    with patch("app.services.customer_client._client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        await get_customer(customer_id)

    sent_headers = mock_client.post.call_args.kwargs["headers"]
    assert sent_headers[INTERNAL_SERVICE_HEADER] == "shared-secret"
