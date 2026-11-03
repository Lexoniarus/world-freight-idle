"""Relational account identity, session and uniqueness boundaries."""

import pytest

from app.domain.errors import DuplicateAccountError
from app.repositories.accounts import AccountRepository


def test_account_repository_preserves_identity_and_session_ownership(
    relational,
):
    accounts = AccountRepository(relational)
    user = accounts.create_user("Carol", "unchanged-test-hash")
    saved = accounts.find_user("carol")

    assert set(user) == {"id", "username"}
    assert saved is not None
    assert saved["password_hash"] == "unchanged-test-hash"
    with pytest.raises(DuplicateAccountError):
        accounts.create_user("CAROL", "different")
    assert accounts.find_user("Carol") == saved
    accounts.save_session("test-token", user["id"], 30)
    assert accounts.session_user("test-token") == user
    accounts.revoke_session("test-token")
    assert accounts.session_user("test-token") is None
