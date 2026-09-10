import pytest

from models.user import UserProfileUpdate

def test_user_profile_update_patch_semantics():

    update = UserProfileUpdate(full_name="Alice Doe")
    dump = update.model_dump(exclude_unset=True)

    assert "full_name" in dump
    assert dump["full_name"] == "Alice Doe"

    assert "last_period_is_approximate" not in dump
