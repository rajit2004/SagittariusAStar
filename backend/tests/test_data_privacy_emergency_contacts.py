import pytest
from unittest.mock import MagicMock

from services.firestore_service import UserService

def test_user_delete_is_idempotent():
    result = UserService.delete_user("nonexistent-user-id")
    assert isinstance(result, dict)
