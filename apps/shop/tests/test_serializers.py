"""Tests for apps.shop.serializers — Product, Purchase, Download serializers."""

from __future__ import annotations
import uuid
import pytest
from rest_framework.test import APIRequestFactory
from apps.shop.models import Product, Purchase, Download
from apps.shop.serializers import (
    DownloadSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    PurchaseCreateSerializer,
    PurchaseSerializer,
)

from conftest import UserFactory


@pytest.fixture
def rf():
    return APIRequestFactory()


def _create_product(**kwargs):
    """Create a Product without triggering UploadThing storage."""

    defaults = {
        "title": "Test Book",
        "description": "A test product",
        "price_tier": "tier_1",
        "is_free": False,
        "category": "books",
        "is_active": True,
    }

    defaults.update(kwargs)

    return Product.objects.create(**defaults)


class TestPurchaseCreateSerializer:
    def test_valid_ios_purchase(self):
        data = {
            "product_id": str(uuid.uuid4()),
            "platform": "ios",
            "receipt_data": "base64-encoded-receipt",
            "transaction_id": "txn_abc123",
        }
        serializer = PurchaseCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_valid_android_purchase(self):
        data = {
            "product_id": str(uuid.uuid4()),
            "platform": "android",
            "receipt_data": "google-purchase-token",
            "transaction_id": "GPA.1234-5678",
        }
        serializer = PurchaseCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_invalid_platform_rejected(self):
        data = {
            "product_id": str(uuid.uuid4()),
            "platform": "windows",
            "receipt_data": "some-data",
            "transaction_id": "txn_123",
        }
        serializer = PurchaseCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "platform" in serializer.errors

    def test_missing_product_id(self):
        data = {
            "platform": "ios",
            "receipt_data": "receipt",
            "transaction_id": "txn_123",
        }
        serializer = PurchaseCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "product_id" in serializer.errors

    def test_missing_receipt_data(self):
        data = {
            "product_id": str(uuid.uuid4()),
            "platform": "ios",
            "transaction_id": "txn_123",
        }
        serializer = PurchaseCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "receipt_data" in serializer.errors

    def test_missing_transaction_id(self):
        data = {
            "product_id": str(uuid.uuid4()),
            "platform": "ios",
            "receipt_data": "receipt",
        }
        serializer = PurchaseCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "transaction_id" in serializer.errors

    def test_invalid_uuid_product_id(self):
        data = {
            "product_id": "not-a-uuid",
            "platform": "ios",
            "receipt_data": "r",
            "transaction_id": "t",
        }
        serializer = PurchaseCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "product_id" in serializer.errors

    def test_empty_receipt_data_rejected(self):
        data = {
            "product_id": str(uuid.uuid4()),
            "platform": "ios",
            "receipt_data": "",
            "transaction_id": "t",
        }
        serializer = PurchaseCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "receipt_data" in serializer.errors

    def test_platform_choices_match_model(self):
        serializer = PurchaseCreateSerializer()
        field_choices = set(dict(serializer.fields["platform"].choices).keys())
        model_choices = {c[0] for c in Purchase.Platform.choices}
        assert field_choices == model_choices


@pytest.mark.django_db
class TestProductListSerializer:
    def test_serializes_product_fields(self):
        product = _create_product()
        serializer = ProductListSerializer(product)
        data = serializer.data
        assert data["title"] == product.title
        assert data["category"] == product.category
        assert data["is_free"] == product.is_free
        assert "created_at" in data

    def test_does_not_include_description(self):
        product = _create_product()
        serializer = ProductListSerializer(product)
        assert "description" not in serializer.data


@pytest.mark.django_db
class TestProductDetailSerializer:
    def test_includes_description(self):
        product = _create_product()
        serializer = ProductDetailSerializer(product, context={"request": None})
        assert "description" in serializer.data

    def test_download_url_none_for_anonymous(self, rf):
        product = _create_product(product_file="shop/test.pdf")
        request = rf.get("/")
        request.user = type("AnonymousUser", (), {"is_anonymous": True})()
        serializer = ProductDetailSerializer(product, context={"request": request})
        assert serializer.data["download_url"] is None

    def test_download_url_for_free_product(self, rf):
        user = UserFactory()
        product = _create_product(is_free=True, product_file="shop/test.pdf")
        request = rf.get("/")
        request.user = user
        serializer = ProductDetailSerializer(product, context={"request": request})
        assert serializer.data["download_url"] is not None

    def test_download_url_for_purchased_product(self, rf):
        user = UserFactory()
        product = _create_product(is_free=False, product_file="shop/test.pdf")
        Purchase.objects.create(
            user=user,
            product=product,
            platform="ios",
            receipt_data="test",
            transaction_id=f"txn_{uuid.uuid4().hex[:16]}",
            is_validated=True,
        )
        request = rf.get("/")
        request.user = user
        serializer = ProductDetailSerializer(product, context={"request": request})
        assert serializer.data["download_url"] is not None

    def test_download_url_none_for_unpurchased(self, rf):
        user = UserFactory()
        product = _create_product(is_free=False, product_file="shop/test.pdf")
        request = rf.get("/")
        request.user = user
        serializer = ProductDetailSerializer(product, context={"request": request})
        assert serializer.data["download_url"] is None

    def test_download_url_none_when_no_product_file(self, rf):
        user = UserFactory()
        product = _create_product(is_free=True)
        request = rf.get("/")
        request.user = user
        serializer = ProductDetailSerializer(product, context={"request": request})
        assert serializer.data["download_url"] is None

    def test_download_url_none_without_request(self):
        product = _create_product()
        serializer = ProductDetailSerializer(product, context={})
        assert serializer.data["download_url"] is None


@pytest.mark.django_db
class TestDownloadSerializer:
    def test_serializes_download_record(self):
        user = UserFactory()
        product = _create_product()
        download = Download.objects.create(user=user, product=product)
        serializer = DownloadSerializer(download)
        data = serializer.data
        assert "id" in data
        assert "product" in data
        assert "created_at" in data
        assert data["product"]["title"] == product.title

    def test_does_not_expose_download_url(self):
        user = UserFactory()
        product = _create_product()
        download = Download.objects.create(user=user, product=product)
        serializer = DownloadSerializer(download)
        assert "download_url" not in serializer.data


@pytest.mark.django_db
class TestPurchaseSerializer:
    def test_serializes_purchase_with_product(self):
        user = UserFactory()
        product = _create_product()
        purchase = Purchase.objects.create(
            user=user,
            product=product,
            platform="ios",
            receipt_data="test",
            transaction_id=f"txn_{uuid.uuid4().hex[:16]}",
            is_validated=True,
        )
        serializer = PurchaseSerializer(purchase)
        data = serializer.data
        assert "id" in data
        assert "product" in data
        assert data["platform"] == "ios"
        assert data["product"]["title"] == product.title
