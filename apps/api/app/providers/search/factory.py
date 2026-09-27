from app.core.config import settings
from app.providers.search.base import SearchProvider
from app.providers.search.mock import MockSearchProvider


def get_search_provider() -> SearchProvider:
    # MVP defaults to MockSearchProvider when in mock mode or search provider is mock
    return MockSearchProvider()
