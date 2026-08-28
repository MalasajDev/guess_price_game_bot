import httpx
import pytest


@pytest.fixture
def client_factory():
    def factory(handler):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    return factory
