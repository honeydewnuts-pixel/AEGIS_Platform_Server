import pytest
from app.services.community_chat_service import CommunityChatService

def test_valid_name():
    assert CommunityChatService.validate_display_name("ApexTrader") == "ApexTrader"

def test_invalid_name():
    with pytest.raises(ValueError):
        CommunityChatService.validate_display_name("ab")
    with pytest.raises(ValueError):
        CommunityChatService.validate_display_name("admin")
    with pytest.raises(ValueError):
        CommunityChatService.validate_display_name("1starts_digit")
