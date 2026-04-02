from __future__ import annotations
import pytest
from apps.accounts.models import User
from apps.common.services import BaseService
from conftest import UserFactory


class UserBaseService(BaseService[User]):
    model = User

    allowed_update_fields = {"full_name"}


@pytest.mark.django_db
class TestBaseServiceUpdate:
    def setup_method(self):
        self.service = UserBaseService()

    def test_update_ignores_disallowed_fields_without_saving_invalid_state(self):
        user = UserFactory(country="US")
        updated = self.service.update(user, email="changed@example.com")
        user.refresh_from_db()
        assert updated.pk == user.pk
        assert user.email != "changed@example.com"

    def test_update_applies_allowed_fields(self):
        user = UserFactory(full_name="Before Name")
        self.service.update(user, full_name="After Name")
        user.refresh_from_db()
        assert user.full_name == "After Name"
