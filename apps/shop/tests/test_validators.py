"""Tests for apps.shop.validators — Apple & Google receipt validation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from apps.shop.validators import validate_apple_receipt, validate_google_receipt


# ════════════════════════════════════════════════════════════════
# Apple receipt validation
# ════════════════════════════════════════════════════════════════


class TestValidateAppleReceipt:
    """Tests for validate_apple_receipt()."""

    @patch("apps.shop.validators.requests.post")
    def test_success_valid_receipt(self, mock_post, settings):
        """A valid receipt with status 0 returns the full result dict."""
        settings.APPLE_SHARED_SECRET = "secret"
        settings.APPLE_BUNDLE_ID = "com.bibleway.io"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": 0,
            "receipt": {
                "bundle_id": "com.bibleway.io",
                "in_app": [
                    {
                        "product_id": "com.bibleway.book1",
                        "purchase_date_ms": "1000",
                    }
                ],
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = validate_apple_receipt(
            "base64-receipt-data",
            expected_product_id="com.bibleway.book1",
        )
        assert result["status"] == 0
        assert result["receipt"]["bundle_id"] == "com.bibleway.io"
        mock_post.assert_called_once()

    @patch("apps.shop.validators.requests.post")
    def test_invalid_receipt_status(self, mock_post, settings):
        """A receipt with a non-zero status raises ValueError."""
        settings.APPLE_SHARED_SECRET = "secret"
        settings.APPLE_BUNDLE_ID = ""

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": 21003}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with pytest.raises(ValueError, match="Apple receipt validation failed: status 21003"):
            validate_apple_receipt("bad-receipt")

    @patch("apps.shop.validators.requests.post")
    def test_wrong_product_id(self, mock_post, settings):
        """Mismatched product_id raises ValueError."""
        settings.APPLE_SHARED_SECRET = "secret"
        settings.APPLE_BUNDLE_ID = "com.bibleway.io"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": 0,
            "receipt": {
                "bundle_id": "com.bibleway.io",
                "in_app": [
                    {
                        "product_id": "com.bibleway.wrong_product",
                        "purchase_date_ms": "1000",
                    }
                ],
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with pytest.raises(ValueError, match="product_id mismatch"):
            validate_apple_receipt(
                "receipt-data",
                expected_product_id="com.bibleway.book1",
            )

    @patch("apps.shop.validators.requests.post")
    def test_wrong_bundle_id(self, mock_post, settings):
        """Mismatched bundle_id raises ValueError."""
        settings.APPLE_SHARED_SECRET = "secret"
        settings.APPLE_BUNDLE_ID = "com.bibleway.io"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": 0,
            "receipt": {
                "bundle_id": "com.other.app",
                "in_app": [],
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with pytest.raises(ValueError, match="bundle_id mismatch"):
            validate_apple_receipt("receipt-data")

    @patch("apps.shop.validators.requests.post")
    def test_no_in_app_transactions(self, mock_post, settings):
        """Receipt with no in_app transactions raises ValueError when product_id expected."""
        settings.APPLE_SHARED_SECRET = "secret"
        settings.APPLE_BUNDLE_ID = "com.bibleway.io"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": 0,
            "receipt": {
                "bundle_id": "com.bibleway.io",
                "in_app": [],
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with pytest.raises(ValueError, match="no in-app transactions"):
            validate_apple_receipt(
                "receipt-data",
                expected_product_id="com.bibleway.book1",
            )

    @patch("apps.shop.validators.requests.post")
    def test_http_error_raises(self, mock_post, settings):
        """An HTTP error from Apple is propagated."""
        settings.APPLE_SHARED_SECRET = "secret"

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_post.return_value = mock_response

        with pytest.raises(requests.HTTPError):
            validate_apple_receipt("receipt-data")

    @patch("apps.shop.validators.requests.post")
    def test_sandbox_receipt_in_debug_mode(self, mock_post, settings):
        """Sandbox receipt (status 21007) retries against sandbox URL when DEBUG=True."""
        settings.APPLE_SHARED_SECRET = "secret"
        settings.APPLE_BUNDLE_ID = ""
        settings.DEBUG = True

        # First call returns sandbox indicator, second call returns valid receipt.
        sandbox_response = MagicMock()
        sandbox_response.json.return_value = {"status": 21007}
        sandbox_response.raise_for_status = MagicMock()

        valid_response = MagicMock()
        valid_response.json.return_value = {
            "status": 0,
            "receipt": {"bundle_id": "com.bibleway.io", "in_app": []},
        }
        valid_response.raise_for_status = MagicMock()

        mock_post.side_effect = [sandbox_response, valid_response]

        result = validate_apple_receipt("receipt-data")
        assert result["status"] == 0
        assert mock_post.call_count == 2

    @patch("apps.shop.validators.requests.post")
    def test_sandbox_receipt_rejected_in_production(self, mock_post, settings):
        """Sandbox receipt (status 21007) is rejected when DEBUG=False."""
        settings.APPLE_SHARED_SECRET = "secret"
        settings.DEBUG = False

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": 21007}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with pytest.raises(ValueError, match="Sandbox receipts are not accepted"):
            validate_apple_receipt("receipt-data")

    @patch("apps.shop.validators.requests.post")
    def test_success_without_expected_product_id(self, mock_post, settings):
        """When no expected_product_id is given, product check is skipped."""
        settings.APPLE_SHARED_SECRET = "secret"
        settings.APPLE_BUNDLE_ID = ""

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": 0,
            "receipt": {"bundle_id": "", "in_app": []},
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = validate_apple_receipt("receipt-data")
        assert result["status"] == 0

    @patch("apps.shop.validators.requests.post")
    def test_latest_transaction_selected(self, mock_post, settings):
        """The transaction with the highest purchase_date_ms is checked."""
        settings.APPLE_SHARED_SECRET = "secret"
        settings.APPLE_BUNDLE_ID = ""

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": 0,
            "receipt": {
                "bundle_id": "",
                "in_app": [
                    {"product_id": "old_product", "purchase_date_ms": "100"},
                    {"product_id": "new_product", "purchase_date_ms": "999"},
                ],
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = validate_apple_receipt(
            "receipt-data",
            expected_product_id="new_product",
        )
        assert result["status"] == 0


# ════════════════════════════════════════════════════════════════
# Google receipt validation
# ════════════════════════════════════════════════════════════════


def _mock_google_modules():
    """Install mock google.oauth2 and googleapiclient into sys.modules."""
    import sys
    mock_sa = MagicMock()
    mock_build = MagicMock()

    # Create module hierarchy
    mock_google = MagicMock()
    mock_google.oauth2.service_account = mock_sa
    sys.modules.setdefault("google", mock_google)
    sys.modules.setdefault("google.oauth2", mock_google.oauth2)
    sys.modules.setdefault("google.oauth2.service_account", mock_sa)

    mock_gapi = MagicMock()
    mock_gapi.discovery.build = mock_build
    sys.modules.setdefault("googleapiclient", mock_gapi)
    sys.modules.setdefault("googleapiclient.discovery", mock_gapi.discovery)

    return mock_sa, mock_build


def _setup_google_mock(api_result, settings):
    """Set up Google receipt mock returning the given result dict."""
    import sys
    settings.GOOGLE_PLAY_CREDENTIALS = {"type": "service_account"}
    settings.ANDROID_PACKAGE_NAME = "com.bibleway.io"

    # Remove cached modules so they get re-created fresh
    for key in list(sys.modules.keys()):
        if key.startswith("google") and key in sys.modules:
            del sys.modules[key]

    mock_sa, mock_build_fn = _mock_google_modules()
    mock_service = MagicMock()
    mock_service.purchases.return_value.products.return_value.get.return_value.execute.return_value = api_result
    mock_build_fn.return_value = mock_service
    return mock_sa, mock_build_fn


class TestValidateGoogleReceipt:
    """Tests for validate_google_receipt()."""

    def test_success_valid_receipt(self, settings):
        _setup_google_mock({
            "purchaseState": 0, "consumptionState": 0, "productId": "com.bibleway.book1",
        }, settings)
        result = validate_google_receipt("com.bibleway.book1", "purchase-token")
        assert result["purchaseState"] == 0
        assert result["productId"] == "com.bibleway.book1"

    def test_invalid_purchase_state_canceled(self, settings):
        _setup_google_mock({
            "purchaseState": 1, "consumptionState": 0, "productId": "com.bibleway.book1",
        }, settings)
        with pytest.raises(ValueError, match="purchaseState=1"):
            validate_google_receipt("com.bibleway.book1", "token")

    def test_already_consumed(self, settings):
        _setup_google_mock({
            "purchaseState": 0, "consumptionState": 1, "productId": "com.bibleway.book1",
        }, settings)
        with pytest.raises(ValueError, match="already been consumed"):
            validate_google_receipt("com.bibleway.book1", "token")

    def test_product_id_mismatch(self, settings):
        _setup_google_mock({
            "purchaseState": 0, "consumptionState": 0, "productId": "com.bibleway.other",
        }, settings)
        with pytest.raises(ValueError, match="product_id mismatch"):
            validate_google_receipt("com.bibleway.book1", "token")

    def test_missing_credentials(self, settings):
        settings.GOOGLE_PLAY_CREDENTIALS = None
        settings.ANDROID_PACKAGE_NAME = "com.bibleway.io"
        with pytest.raises(ValueError, match="credentials not configured"):
            validate_google_receipt("product", "token")

    def test_missing_package_name(self, settings):
        settings.GOOGLE_PLAY_CREDENTIALS = {"type": "service_account"}
        settings.ANDROID_PACKAGE_NAME = ""
        with pytest.raises(ValueError, match="ANDROID_PACKAGE_NAME not configured"):
            validate_google_receipt("product", "token")

    def test_pending_purchase_state(self, settings):
        _setup_google_mock({
            "purchaseState": 2, "consumptionState": 0, "productId": "com.bibleway.book1",
        }, settings)
        with pytest.raises(ValueError, match="purchaseState=2"):
            validate_google_receipt("com.bibleway.book1", "token")

    def test_success_empty_returned_product_id(self, settings):
        _setup_google_mock({
            "purchaseState": 0, "consumptionState": 0, "productId": "",
        }, settings)
        result = validate_google_receipt("com.bibleway.book1", "token")
        assert result["purchaseState"] == 0
