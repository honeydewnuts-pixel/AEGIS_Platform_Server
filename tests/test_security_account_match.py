"""Object-level account match safety."""
import pytest
from fastapi import HTTPException
from app.security import AuthContext, require_account_match


def test_blank_requested_account_rejected():
    auth = AuthContext(account_id="ACC-1", is_admin=False, label=None)
    with pytest.raises(HTTPException) as ei:
        require_account_match(auth, "")
    assert ei.value.status_code == 400


def test_blank_key_account_rejected():
    auth = AuthContext(account_id="", is_admin=False, label=None)
    with pytest.raises(HTTPException) as ei:
        require_account_match(auth, "ACC-1")
    assert ei.value.status_code == 403


def test_mismatch_forbidden():
    auth = AuthContext(account_id="ACC-1", is_admin=False, label=None)
    with pytest.raises(HTTPException) as ei:
        require_account_match(auth, "ACC-2")
    assert ei.value.status_code == 403


def test_match_ok():
    auth = AuthContext(account_id="ACC-1", is_admin=False, label=None)
    require_account_match(auth, "ACC-1")


def test_admin_bypass():
    auth = AuthContext(account_id=None, is_admin=True, label="admin")
    require_account_match(auth, "ANY")
