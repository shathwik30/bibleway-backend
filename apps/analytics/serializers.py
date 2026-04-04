from __future__ import annotations
from rest_framework import serializers
from apps.common.serializers import BaseModelSerializer
from .models import BoostAnalyticSnapshot, PostBoost, PostView


class RecordViewSerializer(serializers.Serializer):
    """Validates input for recording a content view or share."""

    content_type_model = serializers.ChoiceField(
        choices=[("post", "Post"), ("prayer", "Prayer")]
    )

    object_id = serializers.UUIDField()
    view_type = serializers.ChoiceField(
        choices=PostView.ViewType.choices,
        default=PostView.ViewType.VIEW,
    )


class PostAnalyticsSerializer(serializers.Serializer):
    """Read representation of aggregate analytics for a post."""

    views = serializers.IntegerField(read_only=True)
    reactions = serializers.IntegerField(read_only=True)
    comments = serializers.IntegerField(read_only=True)
    shares = serializers.IntegerField(read_only=True)


class PostBoostSerializer(BaseModelSerializer):
    """Full read representation of a post boost.

    ``transaction_id`` is intentionally excluded from the response
    as it is sensitive payment data.
    """

    class Meta:
        model = PostBoost
        fields = [
            "id",
            "post",
            "user",
            "tier",
            "platform",
            "duration_days",
            "is_active",
            "activated_at",
            "expires_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "post",
            "user",
            "is_active",
            "activated_at",
            "expires_at",
            "created_at",
        ]


class PostBoostCreateSerializer(serializers.Serializer):
    """Validates input for activating a post boost."""

    post_id = serializers.UUIDField()
    tier = serializers.CharField(max_length=50)
    platform = serializers.ChoiceField(choices=PostBoost.Platform.choices)
    receipt_data = serializers.CharField()
    transaction_id = serializers.CharField(max_length=255)
    duration_days = serializers.IntegerField(min_value=1, max_value=365)


class BoostAnalyticSnapshotSerializer(BaseModelSerializer):
    """Full read representation of a boost analytics snapshot."""

    class Meta:
        model = BoostAnalyticSnapshot
        fields = [
            "id",
            "boost",
            "impressions",
            "reach",
            "engagement_rate",
            "link_clicks",
            "profile_visits",
            "snapshot_date",
            "created_at",
        ]


class BoostRazorpayOrderCreateSerializer(serializers.Serializer):
    """Input for creating a Razorpay order for a boost."""

    post_id = serializers.UUIDField()
    tier = serializers.CharField(max_length=50)
    duration_days = serializers.IntegerField(min_value=1, max_value=365)


class BoostRazorpayVerifySerializer(serializers.Serializer):
    """Input for verifying a Razorpay payment for a boost."""

    post_id = serializers.UUIDField()
    tier = serializers.CharField(max_length=50)
    duration_days = serializers.IntegerField(min_value=1, max_value=365)
    razorpay_order_id = serializers.CharField(max_length=255)
    razorpay_payment_id = serializers.CharField(max_length=255)
    razorpay_signature = serializers.CharField(max_length=512)
