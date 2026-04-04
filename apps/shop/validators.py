from __future__ import annotations
import hashlib
import hmac
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_APPLE_INVALID_STATUSES = {
    21000,
    21002,
    21003,
    21004,
    21005,
    21006,
    21008,
    21010,
}


def validate_apple_receipt(
    receipt_data: str,
    *,
    expected_product_id: str = "",
) -> dict:
    """Validate receipt with Apple App Store verifyReceipt API.

    Validates:
    - Receipt status is 0 (valid).
    - Bundle ID matches the configured app.
    - Product ID matches the expected product (when provided).
    - Sandbox receipts are rejected in production.

    Returns the full decoded receipt dict on success.
    Raises ``ValueError`` on any validation failure.
    """

    url = "https://buy.itunes.apple.com/verifyReceipt"

    sandbox_url = "https://sandbox.itunes.apple.com/verifyReceipt"

    payload = {
        "receipt-data": receipt_data,
        "password": getattr(settings, "APPLE_SHARED_SECRET", ""),
        "exclude-old-transactions": True,
    }

    response = requests.post(url, json=payload, timeout=30)

    response.raise_for_status()

    result = response.json()

    is_sandbox = result.get("status") == 21007

    if is_sandbox:
        if not getattr(settings, "DEBUG", False):
            raise ValueError("Sandbox receipts are not accepted in production.")

        response = requests.post(sandbox_url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()

    receipt_status = result.get("status")

    if receipt_status != 0:
        raise ValueError(f"Apple receipt validation failed: status {receipt_status}")

    receipt_info = result.get("receipt", {})

    bundle_id = receipt_info.get("bundle_id", "")

    expected_bundle_id = getattr(settings, "APPLE_BUNDLE_ID", "")

    if expected_bundle_id and bundle_id != expected_bundle_id:
        raise ValueError(
            f"Apple receipt bundle_id mismatch: got '{bundle_id}', "
            f"expected '{expected_bundle_id}'."
        )

    if expected_product_id:
        in_app = receipt_info.get("in_app", [])

        if not in_app:
            raise ValueError("Apple receipt contains no in-app transactions.")

        latest_txn = max(in_app, key=lambda t: t.get("purchase_date_ms", "0"))
        actual_product_id = latest_txn.get("product_id", "")

        if actual_product_id != expected_product_id:
            raise ValueError(
                f"Apple receipt product_id mismatch: got '{actual_product_id}', "
                f"expected '{expected_product_id}'."
            )

    return result


def validate_google_receipt(
    product_id: str,
    purchase_token: str,
) -> dict:
    """Validate receipt with Google Play Developer API.

    Validates:
    - Purchase state is 0 (purchased).
    - Purchase has not been consumed (consumptionState == 0).
    - Returned product ID matches the requested product.

    Returns the full purchase resource dict on success.
    Raises ``ValueError`` on any validation failure.
    """

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    credentials_info = getattr(settings, "GOOGLE_PLAY_CREDENTIALS", None)

    if not credentials_info:
        raise ValueError("Google Play credentials not configured")

    package_name = getattr(settings, "ANDROID_PACKAGE_NAME", "")

    if not package_name:
        raise ValueError("ANDROID_PACKAGE_NAME not configured")

    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=["https://www.googleapis.com/auth/androidpublisher"],
    )

    service = build("androidpublisher", "v3", credentials=credentials)

    result = (
        service.purchases()
        .products()
        .get(
            packageName=package_name,
            productId=product_id,
            token=purchase_token,
        )
        .execute()
    )

    purchase_state = result.get("purchaseState")

    if purchase_state != 0:
        raise ValueError(
            f"Google receipt validation failed: purchaseState={purchase_state}"
        )

    consumption_state = result.get("consumptionState", 0)

    if consumption_state != 0:
        raise ValueError(
            "Google receipt has already been consumed (double-spend attempt)."
        )

    returned_product_id = result.get("productId", "")

    if returned_product_id and returned_product_id != product_id:
        raise ValueError(
            f"Google receipt product_id mismatch: got '{returned_product_id}', "
            f"expected '{product_id}'."
        )

    return result


def validate_razorpay_payment(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> None:
    """Validate Razorpay payment signature using HMAC-SHA256.

    Razorpay sends a signature = HMAC_SHA256(order_id|payment_id, secret).
    We recompute it server-side and compare.

    Raises ``ValueError`` on any validation failure.
    """

    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")

    if not key_secret:
        raise ValueError("RAZORPAY_KEY_SECRET is not configured.")

    message = f"{razorpay_order_id}|{razorpay_payment_id}"

    expected_signature = hmac.new(
        key_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, razorpay_signature):
        raise ValueError("Razorpay payment signature verification failed.")
