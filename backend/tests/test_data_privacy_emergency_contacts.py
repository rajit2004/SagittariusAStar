import pytest
from unittest.mock import MagicMock

from services.firestore_service import UserService


def test_user_delete_is_idempotent():
    """Deleting a user that doesn't exist should not raise."""
    result = UserService.delete_user("nonexistent-user-id")
    assert isinstance(result, dict)
