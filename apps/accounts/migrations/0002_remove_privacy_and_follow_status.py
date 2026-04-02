"""Remove privacy settings and follow request status.

All follows are now immediate (no pending state). Privacy fields
(account_visibility, hide_followers_list) have been removed from User.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        # ── Remove old composite indexes that reference `status` ──
        migrations.RemoveIndex(
            model_name="followrelationship",
            name="accounts_fo_followe_ecff01_idx",
        ),
        migrations.RemoveIndex(
            model_name="followrelationship",
            name="accounts_fo_followi_fc8821_idx",
        ),
        # ── Remove the `status` column from FollowRelationship ────
        migrations.RemoveField(
            model_name="followrelationship",
            name="status",
        ),
        # ── Add new single-column indexes ─────────────────────────
        migrations.AddIndex(
            model_name="followrelationship",
            index=models.Index(fields=["follower"], name="accounts_fo_followe_idx"),
        ),
        migrations.AddIndex(
            model_name="followrelationship",
            index=models.Index(fields=["following"], name="accounts_fo_followi_idx"),
        ),
        # ── Remove privacy fields from User ───────────────────────
        migrations.RemoveField(
            model_name="user",
            name="account_visibility",
        ),
        migrations.RemoveField(
            model_name="user",
            name="hide_followers_list",
        ),
    ]
