from __future__ import annotations

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    """Stricter throttle for auth endpoints (login, register, OTP)."""

    scope = "auth"
    rate = "10/minute"


class OTPRateThrottle(AnonRateThrottle):
    """Rate limit OTP requests to prevent abuse."""

    scope = "otp"
    rate = "5/minute"


class PurchaseRateThrottle(UserRateThrottle):
    """Rate limit purchase verification to prevent receipt brute-forcing."""

    scope = "purchase"
    rate = "10/minute"


class BoostRateThrottle(UserRateThrottle):
    """Rate limit boost activation."""

    scope = "boost"
    rate = "10/minute"


class DeviceTokenRateThrottle(UserRateThrottle):
    """Rate limit device token registration."""

    scope = "device_token"
    rate = "10/minute"
