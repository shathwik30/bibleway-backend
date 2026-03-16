"""Tests for admin_panel models: AdminRole, AdminLog, BoostTier."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.admin_panel.models import AdminLog, AdminRole, BoostTier

# Import factories from root conftest (they are available automatically via pytest fixtures,
# but we also use them directly for convenience).
from conftest import (
    AdminLogFactory,
    AdminRoleFactory,
    BoostTierFactory,
    UserFactory,
)


# ---------------------------------------------------------------------------
# AdminRole
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAdminRoleModel:
    """Tests for the AdminRole model."""

    def test_create_admin_role(self):
        """An AdminRole can be created with a valid user and role."""
        role = AdminRoleFactory()
        assert role.pk is not None
        assert role.role == AdminRole.RoleType.SUPER_ADMIN
        assert role.user.is_staff is True

    def test_default_role_is_content_admin(self):
        """When no role is specified at the model level, default is content_admin."""
        user = UserFactory(is_staff=True)
        role = AdminRole.objects.create(user=user)
        assert role.role == AdminRole.RoleType.CONTENT_ADMIN

    def test_role_choices(self):
        """All expected role choices exist."""
        choices = {c[0] for c in AdminRole.RoleType.choices}
        assert "super_admin" in choices
        assert "content_admin" in choices
        assert "moderation_admin" in choices

    def test_one_to_one_constraint(self):
        """A user can have at most one AdminRole (OneToOne)."""
        role = AdminRoleFactory()
        with pytest.raises(IntegrityError):
            AdminRole.objects.create(user=role.user, role="content_admin")

    def test_str_representation(self):
        """__str__ includes the user's full_name and the role display."""
        role = AdminRoleFactory(role="moderation_admin")
        result = str(role)
        assert role.user.full_name in result
        assert "Moderation Admin" in result

    def test_cascade_delete_user(self):
        """Deleting the user cascades to delete the AdminRole."""
        role = AdminRoleFactory()
        user_pk = role.user.pk
        role.user.delete()
        assert not AdminRole.objects.filter(user_id=user_pk).exists()


# ---------------------------------------------------------------------------
# AdminLog
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAdminLogModel:
    """Tests for the AdminLog model."""

    def test_create_admin_log(self):
        """An AdminLog can be created with the factory defaults."""
        log = AdminLogFactory()
        assert log.pk is not None
        assert log.action == AdminLog.ActionType.CREATE
        assert log.target_model == "accounts.User"
        assert log.detail == "Test log entry"
        assert log.metadata == {}

    def test_action_choices(self):
        """All expected action types exist."""
        choices = {c[0] for c in AdminLog.ActionType.choices}
        expected = {
            "create", "update", "delete", "suspend", "unsuspend",
            "warn", "dismiss_report", "remove_content", "broadcast",
            "role_change",
        }
        assert expected.issubset(choices)

    def test_ordering_is_newest_first(self):
        """Logs are ordered by -created_at by default."""
        log1 = AdminLogFactory()
        log2 = AdminLogFactory()
        logs = list(AdminLog.objects.all())
        # log2 was created after log1, so it should appear first.
        assert logs[0].pk == log2.pk
        assert logs[1].pk == log1.pk

    def test_str_representation(self):
        """__str__ includes admin full_name, action, target_model:target_id."""
        log = AdminLogFactory(action="suspend", target_model="accounts.User")
        result = str(log)
        assert log.admin_user.full_name in result
        assert "suspend" in result
        assert "accounts.User" in result

    def test_metadata_json_field(self):
        """Metadata can store arbitrary JSON."""
        metadata = {"old_role": "content_admin", "new_role": "super_admin"}
        log = AdminLogFactory(metadata=metadata)
        log.refresh_from_db()
        assert log.metadata == metadata

    def test_cascade_delete_admin_user(self):
        """Deleting the admin_user cascades to delete their logs."""
        log = AdminLogFactory()
        user_pk = log.admin_user.pk
        log.admin_user.delete()
        assert not AdminLog.objects.filter(admin_user_id=user_pk).exists()


# ---------------------------------------------------------------------------
# BoostTier
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBoostTierModel:
    """Tests for the BoostTier model."""

    def test_create_boost_tier(self):
        """A BoostTier can be created with the factory defaults."""
        tier = BoostTierFactory()
        assert tier.pk is not None
        assert tier.duration_days == 7
        assert tier.display_price == "$5.00"
        assert tier.is_active is True

    def test_unique_apple_product_id(self):
        """apple_product_id must be unique."""
        BoostTierFactory(apple_product_id="com.app.boost_a")
        with pytest.raises(IntegrityError):
            BoostTierFactory(apple_product_id="com.app.boost_a")

    def test_unique_google_product_id(self):
        """google_product_id must be unique."""
        BoostTierFactory(google_product_id="com.app.boost_g")
        with pytest.raises(IntegrityError):
            BoostTierFactory(google_product_id="com.app.boost_g")

    def test_ordering_by_duration_days(self):
        """Tiers are ordered by duration_days."""
        tier_long = BoostTierFactory(duration_days=30)
        tier_short = BoostTierFactory(duration_days=3)
        tier_mid = BoostTierFactory(duration_days=14)
        tiers = list(BoostTier.objects.all())
        assert tiers[0].pk == tier_short.pk
        assert tiers[1].pk == tier_mid.pk
        assert tiers[2].pk == tier_long.pk

    def test_str_representation(self):
        """__str__ includes name, duration_days, and display_price."""
        tier = BoostTierFactory(
            name="Premium Boost",
            duration_days=14,
            display_price="$9.99",
        )
        result = str(tier)
        assert "Premium Boost" in result
        assert "14 days" in result
        assert "$9.99" in result

    def test_is_active_default_true(self):
        """is_active defaults to True."""
        tier = BoostTierFactory()
        assert tier.is_active is True

    def test_timestamps_present(self):
        """BoostTier inherits TimeStampedModel: has created_at and updated_at."""
        tier = BoostTierFactory()
        assert tier.created_at is not None
        assert tier.updated_at is not None
