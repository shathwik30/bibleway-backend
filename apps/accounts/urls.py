from __future__ import annotations

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns: list = [
    # ── Registration & Authentication ────────────────────────────
    path(
        "register/",
        views.UserRegistrationView.as_view(),
        name="register",
    ),
    path(
        "login/",
        views.UserLoginView.as_view(),
        name="login",
    ),
    path(
        "logout/",
        views.UserLogoutView.as_view(),
        name="logout",
    ),
    path(
        "token/refresh/",
        views.TokenRefreshView.as_view(),
        name="token-refresh",
    ),
    # ── Email Verification ───────────────────────────────────────
    path(
        "verify-email/",
        views.EmailVerificationView.as_view(),
        name="verify-email",
    ),
    path(
        "auth/resend-otp/",
        views.ResendOTPView.as_view(),
        name="resend-otp",
    ),
    # ── Password Management ──────────────────────────────────────
    path(
        "password-reset/",
        views.PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),
    path(
        "password-reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path(
        "change-password/",
        views.ChangePasswordView.as_view(),
        name="change-password",
    ),
    # ── User Profile ─────────────────────────────────────────────
    path(
        "profile/",
        views.UserProfileView.as_view(),
        name="profile",
    ),
    path(
        "users/search/",
        views.UserSearchView.as_view(),
        name="user-search",
    ),
    path(
        "users/<uuid:user_id>/",
        views.UserDetailView.as_view(),
        name="user-detail",
    ),
    # ── Follow Management ────────────────────────────────────────
    path(
        "users/<uuid:user_id>/follow/",
        views.FollowView.as_view(),
        name="follow",
    ),
    path(
        "users/<uuid:user_id>/followers/",
        views.FollowersListView.as_view(),
        name="followers-list",
    ),
    path(
        "users/<uuid:user_id>/following/",
        views.FollowingListView.as_view(),
        name="following-list",
    ),
    path(
        "follow-requests/",
        views.PendingFollowRequestsListView.as_view(),
        name="pending-follow-requests",
    ),
    path(
        "follow-requests/<uuid:user_id>/",
        views.FollowRequestView.as_view(),
        name="follow-request-respond",
    ),
    # ── Block Management ─────────────────────────────────────────
    path(
        "users/<uuid:user_id>/block/",
        views.BlockView.as_view(),
        name="block",
    ),
    path(
        "blocked-users/",
        views.BlockedUsersListView.as_view(),
        name="blocked-users-list",
    ),
    # ── Privacy Settings ─────────────────────────────────────────
    path(
        "privacy/",
        views.PrivacySettingsView.as_view(),
        name="privacy-settings",
    ),
]
