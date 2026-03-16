from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.serializers import BaseModelSerializer, BaseTimestampedSerializer

from .models import Download, Product, Purchase


# ---------------------------------------------------------------------------
# Product serializers
# ---------------------------------------------------------------------------


class ProductListSerializer(BaseTimestampedSerializer):
    """Compact product representation for list / browse endpoints."""

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "cover_image",
            "category",
            "is_free",
            "price_tier",
            "apple_product_id",
            "google_product_id",
            "created_at",
        ]


class ProductDetailSerializer(BaseTimestampedSerializer):
    """Full product detail.

    The ``product_file`` URL is only exposed when the requesting user has
    purchased the product (or it is free).  This is controlled by the
    ``download_url`` field populated via context in the view layer.
    """

    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "description",
            "cover_image",
            "category",
            "is_free",
            "price_tier",
            "apple_product_id",
            "google_product_id",
            "download_count",
            "download_url",
            "created_at",
            "updated_at",
        ]

    def get_download_url(self, obj: Product) -> str | None:
        """Return the download endpoint URL for eligible users.

        For both free and paid products, we return the download endpoint URL
        so the client always goes through the proper download flow (which
        records the download event and generates a fresh pre-signed URL).
        """
        request = self.context.get("request")
        if request is None or not hasattr(request, "user") or request.user.is_anonymous:
            return None

        if not obj.product_file:
            return None

        if obj.is_free:
            # Point to the download endpoint rather than exposing the raw file URL
            return request.build_absolute_uri(f"/api/shop/downloads/{obj.pk}/")

        has_purchased = Purchase.objects.filter(
            user=request.user,
            product=obj,
            is_validated=True,
        ).exists()
        if has_purchased:
            return request.build_absolute_uri(f"/api/shop/downloads/{obj.pk}/")
        return None


# ---------------------------------------------------------------------------
# Purchase serializers
# ---------------------------------------------------------------------------


class PurchaseCreateSerializer(serializers.Serializer):
    """Validates input for verifying and recording a purchase."""

    product_id = serializers.UUIDField()
    platform = serializers.ChoiceField(choices=Purchase.Platform.choices)
    receipt_data = serializers.CharField()
    transaction_id = serializers.CharField(max_length=255)


class ProductInlinePurchaseSerializer(serializers.Serializer):
    """Minimal product representation nested inside a purchase."""

    id = serializers.UUIDField(read_only=True)
    title = serializers.CharField(read_only=True)
    cover_image = serializers.ImageField(read_only=True)
    category = serializers.CharField(read_only=True)
    is_free = serializers.BooleanField(read_only=True)


class PurchaseSerializer(BaseModelSerializer):
    """Read representation of a purchase with nested product info."""

    product = ProductInlinePurchaseSerializer(read_only=True)

    class Meta:
        model = Purchase
        fields = [
            "id",
            "product",
            "platform",
            "transaction_id",
            "is_validated",
            "created_at",
        ]


# ---------------------------------------------------------------------------
# Download serializers
# ---------------------------------------------------------------------------


class DownloadSerializer(BaseModelSerializer):
    """Read representation of a download record with product info.

    The download_url is intentionally omitted from stored download records.
    Fresh pre-signed URLs should only be generated on demand via the
    download endpoint to avoid leaking long-lived URLs.
    """

    product = ProductInlinePurchaseSerializer(read_only=True)

    class Meta:
        model = Download
        fields = [
            "id",
            "product",
            "created_at",
        ]
