"""Tests for apps.shop.services — ProductService, PurchaseService, DownloadService."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from rest_framework.exceptions import ValidationError

from apps.common.exceptions import BadRequestError, ConflictError, NotFoundError
from apps.shop.models import Download, Product, Purchase
from apps.shop.services import DownloadService, ProductService, PurchaseService


# ---------------------------------------------------------------------------
# Helper: create a Product without triggering UploadThing storage
# ---------------------------------------------------------------------------


def _create_product(**kwargs):
    """Create a Product row directly, bypassing FileField storage backends."""
    defaults = {
        "title": "Test Product",
        "description": "A test product description.",
        "cover_image": "shop/fake/cover.jpg",  # just a string path
        "product_file": "shop/fake/product.pdf",
        "price_tier": "tier_1",
        "is_free": False,
        "category": "books",
        "is_active": True,
    }
    defaults.update(kwargs)
    return Product.objects.create(**defaults)


def _create_purchase(user, product, **kwargs):
    """Create a Purchase row directly."""
    defaults = {
        "user": user,
        "product": product,
        "platform": "ios",
        "receipt_data": "test-receipt-data",
        "transaction_id": f"txn_{uuid4().hex[:16]}",
        "is_validated": True,
    }
    defaults.update(kwargs)
    return Purchase.objects.create(**defaults)


def _create_download(user, product, purchase=None, **kwargs):
    """Create a Download row directly."""
    return Download.objects.create(
        user=user, product=product, purchase=purchase, **kwargs
    )


# ---------------------------------------------------------------------------
# ProductService
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProductServiceListActive:
    def setup_method(self):
        self.service = ProductService()

    def test_returns_active_products(self):
        _create_product(title="Active 1", is_active=True, category="books")
        _create_product(title="Active 2", is_active=True, category="books")
        _create_product(title="Inactive", is_active=False, category="books")

        products = self.service.list_active_products()
        assert products.count() == 2

    def test_filter_by_category(self):
        _create_product(title="Book", is_active=True, category="books")
        _create_product(title="Song", is_active=True, category="music")

        products = self.service.list_active_products(category="books")
        assert products.count() == 1
        assert products.first().category == "books"

    def test_no_category_returns_all_active(self):
        _create_product(title="Book", is_active=True, category="books")
        _create_product(title="Song", is_active=True, category="music")

        products = self.service.list_active_products()
        assert products.count() == 2

    def test_excludes_inactive(self):
        _create_product(is_active=False)
        products = self.service.list_active_products()
        assert products.count() == 0


@pytest.mark.django_db
class TestProductServiceDetail:
    def setup_method(self):
        self.service = ProductService()

    def test_get_product_detail(self):
        product = _create_product(is_active=True)
        result = self.service.get_product_detail(product_id=product.id)
        assert result.pk == product.pk

    def test_get_inactive_product_raises(self):
        product = _create_product(is_active=False)
        with pytest.raises(NotFoundError):
            self.service.get_product_detail(product_id=product.id)

    def test_get_nonexistent_raises(self):
        with pytest.raises(NotFoundError):
            self.service.get_product_detail(product_id=uuid4())


@pytest.mark.django_db
class TestProductServiceSearch:
    def setup_method(self):
        self.service = ProductService()

    def test_search_by_title(self):
        _create_product(title="Bible Study Guide", is_active=True)
        _create_product(title="Prayer Journal", is_active=True)

        results = self.service.search_products(query="Bible")
        assert results.count() == 1

    def test_search_by_description(self):
        _create_product(
            title="Product A",
            description="Contains worship songs",
            is_active=True,
        )
        results = self.service.search_products(query="worship")
        assert results.count() == 1

    def test_search_case_insensitive(self):
        _create_product(title="DAILY DEVOTIONS", is_active=True)
        results = self.service.search_products(query="daily")
        assert results.count() == 1

    def test_empty_query_raises(self):
        with pytest.raises(BadRequestError, match="must not be empty"):
            self.service.search_products(query="")

    def test_whitespace_query_raises(self):
        with pytest.raises(BadRequestError, match="must not be empty"):
            self.service.search_products(query="   ")

    def test_no_results(self):
        _create_product(title="Something Else", is_active=True)
        results = self.service.search_products(query="nonexistent")
        assert results.count() == 0


# ---------------------------------------------------------------------------
# PurchaseService
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPurchaseServiceVerify:
    def setup_method(self):
        self.service = PurchaseService()

    @patch("apps.shop.services.validate_apple_receipt")
    def test_verify_purchase_ios(self, mock_validate, user):
        mock_validate.return_value = {"status": 0}
        product = _create_product(is_active=True, apple_product_id="com.app.product1")

        purchase = self.service.verify_purchase(
            user_id=user.id,
            product_id=product.id,
            platform="ios",
            receipt_data="apple-receipt-data",
            transaction_id="txn_unique_001",
        )

        assert isinstance(purchase, Purchase)
        assert purchase.is_validated is True
        assert purchase.transaction_id == "txn_unique_001"
        mock_validate.assert_called_once()

    @patch("apps.shop.services.validate_google_receipt")
    def test_verify_purchase_android(self, mock_validate, user):
        mock_validate.return_value = {"purchaseState": 0}
        product = _create_product(
            is_active=True,
            google_product_id="com.app.product.android",
            apple_product_id="com.app.product.apple",
        )

        purchase = self.service.verify_purchase(
            user_id=user.id,
            product_id=product.id,
            platform="android",
            receipt_data="google-purchase-token",
            transaction_id="txn_unique_002",
        )
        assert purchase.is_validated is True
        mock_validate.assert_called_once()

    @patch("apps.shop.services.validate_apple_receipt")
    def test_duplicate_transaction_id_rejected(self, mock_validate, user):
        mock_validate.return_value = {"status": 0}
        product = _create_product(is_active=True)

        self.service.verify_purchase(
            user_id=user.id,
            product_id=product.id,
            platform="ios",
            receipt_data="receipt1",
            transaction_id="txn_dup",
        )

        with pytest.raises(ConflictError, match="already been processed"):
            self.service.verify_purchase(
                user_id=user.id,
                product_id=product.id,
                platform="ios",
                receipt_data="receipt2",
                transaction_id="txn_dup",
            )

    def test_inactive_product_raises(self, user):
        product = _create_product(is_active=False)
        with pytest.raises(NotFoundError, match="not found or inactive"):
            self.service.verify_purchase(
                user_id=user.id,
                product_id=product.id,
                platform="ios",
                receipt_data="receipt",
                transaction_id="txn_001",
            )

    def test_nonexistent_product_raises(self, user):
        with pytest.raises(NotFoundError):
            self.service.verify_purchase(
                user_id=user.id,
                product_id=uuid4(),
                platform="ios",
                receipt_data="receipt",
                transaction_id="txn_002",
            )

    @patch("apps.shop.services.validate_apple_receipt")
    def test_receipt_validation_failure_raises(self, mock_validate, user):
        mock_validate.side_effect = ValueError("Invalid receipt")
        product = _create_product(is_active=True)

        with pytest.raises(ValidationError, match="Receipt validation failed"):
            self.service.verify_purchase(
                user_id=user.id,
                product_id=product.id,
                platform="ios",
                receipt_data="bad-receipt",
                transaction_id="txn_003",
            )

    @patch("apps.shop.services.validate_apple_receipt")
    def test_increments_download_count(self, mock_validate, user):
        mock_validate.return_value = {"status": 0}
        product = _create_product(is_active=True, download_count=0)

        self.service.verify_purchase(
            user_id=user.id,
            product_id=product.id,
            platform="ios",
            receipt_data="receipt",
            transaction_id="txn_inc",
        )

        product.refresh_from_db()
        assert product.download_count == 1


@pytest.mark.django_db
class TestPurchaseServiceList:
    def setup_method(self):
        self.service = PurchaseService()

    def test_list_user_purchases(self, user, user2):
        product = _create_product(is_active=True)
        _create_purchase(user, product, transaction_id="txn_a")
        _create_purchase(user, product, transaction_id="txn_b")
        _create_purchase(user2, product, transaction_id="txn_c")  # other user

        purchases = self.service.list_user_purchases(user_id=user.id)
        assert purchases.count() == 2

    def test_list_empty(self, user):
        purchases = self.service.list_user_purchases(user_id=user.id)
        assert purchases.count() == 0


# ---------------------------------------------------------------------------
# DownloadService
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDownloadServiceRecord:
    def setup_method(self):
        self.service = DownloadService()

    def test_record_download_free_product(self, user):
        product = _create_product(is_active=True, is_free=True)
        download = self.service.record_download(
            user_id=user.id, product_id=product.id, purchase_id=None
        )
        assert isinstance(download, Download)
        assert download.purchase is None

    def test_record_download_paid_with_purchase(self, user):
        product = _create_product(is_active=True, is_free=False)
        purchase = _create_purchase(user, product, is_validated=True)

        download = self.service.record_download(
            user_id=user.id,
            product_id=product.id,
            purchase_id=purchase.id,
        )
        assert download.purchase_id == purchase.id

    def test_paid_product_without_purchase_raises(self, user):
        product = _create_product(is_active=True, is_free=False)
        with pytest.raises(BadRequestError, match="purchase is required"):
            self.service.record_download(
                user_id=user.id, product_id=product.id, purchase_id=None
            )

    def test_nonexistent_product_raises(self, user):
        with pytest.raises(NotFoundError):
            self.service.record_download(
                user_id=user.id, product_id=uuid4(), purchase_id=None
            )

    def test_purchase_not_belonging_to_user_raises(self, user, user2):
        product = _create_product(is_active=True, is_free=False)
        purchase = _create_purchase(user2, product, is_validated=True)

        with pytest.raises(NotFoundError, match="does not belong"):
            self.service.record_download(
                user_id=user.id,
                product_id=product.id,
                purchase_id=purchase.id,
            )

    def test_inactive_product_raises(self, user):
        product = _create_product(is_active=False, is_free=True)
        with pytest.raises(NotFoundError):
            self.service.record_download(
                user_id=user.id, product_id=product.id, purchase_id=None
            )


@pytest.mark.django_db
class TestDownloadServiceList:
    def setup_method(self):
        self.service = DownloadService()

    def test_list_user_downloads(self, user, user2):
        product = _create_product(is_active=True, is_free=True)
        _create_download(user, product)
        _create_download(user, product)
        _create_download(user2, product)  # other user

        downloads = self.service.list_user_downloads(user_id=user.id)
        assert downloads.count() == 2

    def test_list_empty(self, user):
        downloads = self.service.list_user_downloads(user_id=user.id)
        assert downloads.count() == 0
