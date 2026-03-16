from __future__ import annotations

from typing import Any
from uuid import UUID

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.pagination import StandardPageNumberPagination
from apps.common.views import BaseAPIView

from .permissions import IsAdminStaff, IsContentAdmin, IsModerationAdmin, IsSuperAdmin
from .serializers import (
    AdminBoostRevenueSerializer,
    AdminBoostSerializer,
    AdminBoostSnapshotSerializer,
    AdminBoostTierCreateSerializer,
    AdminBoostTierSerializer,
    AdminBoostTierUpdateSerializer,
    AdminBroadcastCreateSerializer,
    AdminBroadcastSerializer,
    AdminChapterCreateSerializer,
    AdminChapterReorderSerializer,
    AdminChapterSerializer,
    AdminChapterUpdateSerializer,
    AdminContentEngagementSerializer,
    AdminCreateAdminSerializer,
    AdminDemographicsSerializer,
    AdminLogSerializer,
    AdminPageCreateSerializer,
    AdminPageSerializer,
    AdminPageUpdateSerializer,
    AdminProductCreateSerializer,
    AdminProductSerializer,
    AdminProductStatsSerializer,
    AdminProductUpdateSerializer,
    AdminPurchaseSerializer,
    AdminReportActionSerializer,
    AdminReportDetailSerializer,
    AdminReportListSerializer,
    AdminRoleSerializer,
    AdminRoleUpdateSerializer,
    AdminSectionCreateSerializer,
    AdminSectionSerializer,
    AdminSectionUpdateSerializer,
    AdminShopRevenueSerializer,
    AdminUserDetailSerializer,
    AdminUserListSerializer,
    AdminUserSuspendSerializer,
    AdminVerseBulkCreateSerializer,
    AdminVerseFallbackCreateSerializer,
    AdminVerseFallbackUpdateSerializer,
    AdminVerseFallbackSerializer,
    AdminVerseOfDayCreateSerializer,
    AdminVerseOfDaySerializer,
    AdminVerseOfDayUpdateSerializer,
    DashboardOverviewSerializer,
    UserGrowthPointSerializer,
)
from .services import (
    AdminAnalyticsService,
    AdminBibleService,
    AdminBoostService,
    AdminBroadcastService,
    AdminDashboardService,
    AdminLogService,
    AdminModerationService,
    AdminShopService,
    AdminUserService,
    AdminVerseService,
)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class DashboardOverviewView(BaseAPIView):
    """Return high-level KPI overview for the admin dashboard."""

    permission_classes: list[type[BasePermission]] = [IsAdminStaff]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminDashboardService()

    def get(self, request: Request) -> Response:
        data: dict[str, Any] = self.service.get_overview()
        serializer = DashboardOverviewSerializer(data)
        return self.success_response(data=serializer.data, message="Dashboard overview retrieved")


class UserGrowthView(BaseAPIView):
    """Return user-growth data points over a configurable window."""

    permission_classes: list[type[BasePermission]] = [IsAdminStaff]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminDashboardService()

    def get(self, request: Request) -> Response:
        try:
            days: int = int(request.query_params.get("days", 30))
        except (TypeError, ValueError):
            days = 30
        data: list[dict[str, Any]] = self.service.get_user_growth_data(days=days)
        serializer = UserGrowthPointSerializer(data, many=True)
        return self.success_response(data=serializer.data, message="User growth data retrieved")


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------


class AdminUserListView(BaseAPIView):
    """Paginated list of all users with search / filter / ordering."""

    permission_classes: list[type[BasePermission]] = [IsModerationAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminUserService()
        self.paginator = StandardPageNumberPagination()

    def get(self, request: Request) -> Response:
        filters: dict[str, Any] = {
            "search": request.query_params.get("search"),
            "country": request.query_params.get("country"),
            "is_active": request.query_params.get("is_active"),
            "ordering": request.query_params.get("ordering"),
        }
        queryset = self.service.list_users(
            search=filters.get("search"),
            country=filters.get("country"),
            is_active=filters.get("is_active"),
            ordering=filters.get("ordering"),
        )
        page = self.paginator.paginate_queryset(queryset, request, view=self)
        serializer = AdminUserListSerializer(page, many=True)
        return self.paginator.get_paginated_response(serializer.data)


class AdminUserDetailView(BaseAPIView):
    """Retrieve detailed information about a single user."""

    permission_classes: list[type[BasePermission]] = [IsModerationAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminUserService()

    def get(self, request: Request, user_id: UUID) -> Response:
        user = self.service.get_user_detail(user_id=user_id)
        serializer = AdminUserDetailSerializer(user)
        return self.success_response(data=serializer.data, message="User detail retrieved")


class AdminUserSuspendView(BaseAPIView):
    """Suspend a user with an attached reason."""

    permission_classes: list[type[BasePermission]] = [IsModerationAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminUserService()

    def post(self, request: Request, user_id: UUID) -> Response:
        serializer = AdminUserSuspendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.service.suspend_user(
            admin_user=request.user,
            user_id=user_id,
            reason=serializer.validated_data.get("reason", ""),
        )
        return self.success_response(
            data=AdminUserDetailSerializer(user).data,
            message="User suspended",
        )


class AdminUserUnsuspendView(BaseAPIView):
    """Remove suspension from a user."""

    permission_classes: list[type[BasePermission]] = [IsModerationAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminUserService()

    def post(self, request: Request, user_id: UUID) -> Response:
        user = self.service.unsuspend_user(admin_user=request.user, user_id=user_id)
        return self.success_response(
            data=AdminUserDetailSerializer(user).data,
            message="User unsuspended",
        )


# ---------------------------------------------------------------------------
# Admin User Management (Super Admin only)
# ---------------------------------------------------------------------------


class AdminUsersListView(BaseAPIView):
    """List all admin staff users."""

    permission_classes: list[type[BasePermission]] = [IsSuperAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminUserService()

    def get(self, request: Request) -> Response:
        admins = self.service.list_admin_users()
        serializer = AdminRoleSerializer(admins, many=True)
        return self.success_response(data=serializer.data, message="Admin users retrieved")


class AdminUserCreateView(BaseAPIView):
    """Create a new admin user."""

    permission_classes: list[type[BasePermission]] = [IsSuperAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminUserService()

    def post(self, request: Request) -> Response:
        serializer = AdminCreateAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        admin = self.service.create_admin_user(
            admin_user=request.user,
            email=data["email"],
            password=data["password"],
            full_name=data["full_name"],
            role=data["role"],
        )
        return self.created_response(
            data=AdminRoleSerializer(admin).data,
            message="Admin user created",
        )


class AdminUserRoleUpdateView(BaseAPIView):
    """Update the role of an existing admin user."""

    permission_classes: list[type[BasePermission]] = [IsSuperAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminUserService()

    def put(self, request: Request, user_id: UUID) -> Response:
        serializer = AdminRoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin = self.service.update_admin_role(
            admin_user=request.user,
            target_user_id=user_id,
            new_role=serializer.validated_data["role"],
        )
        return self.success_response(
            data=AdminRoleSerializer(admin).data,
            message="Admin role updated",
        )


class AdminUserDeleteView(BaseAPIView):
    """Remove admin privileges from a user."""

    permission_classes: list[type[BasePermission]] = [IsSuperAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminUserService()

    def delete(self, request: Request, user_id: UUID) -> Response:
        self.service.delete_admin_user(admin_user=request.user, target_user_id=user_id)
        return self.no_content_response()


# ---------------------------------------------------------------------------
# Content Moderation
# ---------------------------------------------------------------------------


class AdminReportListView(BaseAPIView):
    """Paginated list of user reports with optional filters."""

    permission_classes: list[type[BasePermission]] = [IsModerationAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminModerationService()
        self.paginator = StandardPageNumberPagination()

    def get(self, request: Request) -> Response:
        queryset = self.service.list_reports(
            status=request.query_params.get("status"),
            content_type=request.query_params.get("content_type"),
        )
        page = self.paginator.paginate_queryset(queryset, request, view=self)
        serializer = AdminReportListSerializer(page, many=True)
        return self.paginator.get_paginated_response(serializer.data)


class AdminReportDetailView(BaseAPIView):
    """Retrieve details for a single report."""

    permission_classes: list[type[BasePermission]] = [IsModerationAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminModerationService()

    def get(self, request: Request, report_id: UUID) -> Response:
        report = self.service.get_report_detail(report_id=report_id)
        serializer = AdminReportDetailSerializer(report)
        return self.success_response(data=serializer.data, message="Report detail retrieved")


class AdminReportActionView(BaseAPIView):
    """Take an action on a reported piece of content."""

    permission_classes: list[type[BasePermission]] = [IsModerationAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminModerationService()

    def post(self, request: Request, report_id: UUID) -> Response:
        serializer = AdminReportActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        action = data["action"]
        admin_user = request.user

        if action == "dismiss":
            report = self.service.dismiss_report(
                admin_user=admin_user, report_id=report_id,
            )
        elif action == "remove_content":
            report = self.service.remove_content(
                admin_user=admin_user, report_id=report_id,
            )
        elif action == "warn":
            report = self.service.warn_user(
                admin_user=admin_user,
                report_id=report_id,
                warning_message=data.get("warning_message", ""),
            )
        elif action == "suspend":
            report = self.service.suspend_from_report(
                admin_user=admin_user, report_id=report_id,
            )
        else:
            from apps.common.exceptions import BadRequestError
            raise BadRequestError(detail=f"Unknown action: {action}")

        return self.success_response(
            data=AdminReportDetailSerializer(report).data,
            message="Report action completed",
        )


# ---------------------------------------------------------------------------
# Verse of the Day
# ---------------------------------------------------------------------------


class AdminVerseListView(BaseAPIView):
    """Paginated list of scheduled verse-of-the-day entries."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminVerseService()
        self.paginator = StandardPageNumberPagination()

    def get(self, request: Request) -> Response:
        queryset = self.service.list_verses()
        page = self.paginator.paginate_queryset(queryset, request, view=self)
        serializer = AdminVerseOfDaySerializer(page, many=True)
        return self.paginator.get_paginated_response(serializer.data)


class AdminVerseCreateView(BaseAPIView):
    """Create a new verse-of-the-day entry."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminVerseService()

    def post(self, request: Request) -> Response:
        serializer = AdminVerseOfDayCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        verse = self.service.create_verse(**data, admin_user=request.user)
        return self.created_response(
            data=AdminVerseOfDaySerializer(verse).data,
            message="Verse of the day created",
        )


class AdminVerseUpdateView(BaseAPIView):
    """Update an existing verse-of-the-day entry."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminVerseService()

    def put(self, request: Request, verse_id: UUID) -> Response:
        serializer = AdminVerseOfDayUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        verse = self.service.update_verse(
            verse_id=verse_id,
            **data,
            admin_user=request.user,
        )
        return self.success_response(
            data=AdminVerseOfDaySerializer(verse).data,
            message="Verse of the day updated",
        )

    def delete(self, request: Request, verse_id: UUID) -> Response:
        """Delegate to AdminVerseDeleteView logic at the same URL path."""
        self.service.delete_verse(verse_id=verse_id, admin_user=request.user)
        return self.no_content_response()


class AdminVerseDeleteView(BaseAPIView):
    """Delete a verse-of-the-day entry."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminVerseService()

    def delete(self, request: Request, verse_id: UUID) -> Response:
        self.service.delete_verse(verse_id=verse_id, admin_user=request.user)
        return self.no_content_response()


class AdminVerseBulkCreateView(BaseAPIView):
    """Bulk-create multiple verse-of-the-day entries at once."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminVerseService()

    def post(self, request: Request) -> Response:
        serializer = AdminVerseBulkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        verses = self.service.bulk_create_verses(
            **data,
            admin_user=request.user,
        )
        return self.created_response(
            data=AdminVerseOfDaySerializer(verses, many=True).data,
            message="Verses created in bulk",
        )


class AdminFallbackPoolListView(BaseAPIView):
    """List all fallback pool verses."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminVerseService()

    def get(self, request: Request) -> Response:
        verses = self.service.list_fallback_pool()
        serializer = AdminVerseFallbackSerializer(verses, many=True)
        return self.success_response(data=serializer.data, message="Fallback verses retrieved")


class AdminFallbackPoolCreateView(BaseAPIView):
    """Add a verse to the fallback pool."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminVerseService()

    def post(self, request: Request) -> Response:
        serializer = AdminVerseFallbackCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        verse = self.service.create_fallback_verse(
            **data,
            admin_user=request.user,
        )
        return self.created_response(
            data=AdminVerseFallbackSerializer(verse).data,
            message="Fallback verse created",
        )


class AdminFallbackPoolUpdateView(BaseAPIView):
    """Update a fallback pool verse."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminVerseService()

    def put(self, request: Request, verse_id: UUID) -> Response:
        serializer = AdminVerseFallbackUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        verse = self.service.update_fallback_verse(
            verse_id=verse_id,
            **data,
            admin_user=request.user,
        )
        return self.success_response(
            data=AdminVerseFallbackSerializer(verse).data,
            message="Fallback verse updated",
        )

    def delete(self, request: Request, verse_id: UUID) -> Response:
        """Delegate to AdminFallbackPoolDeleteView logic at the same URL path."""
        self.service.delete_fallback_verse(verse_id=verse_id, admin_user=request.user)
        return self.no_content_response()


class AdminFallbackPoolDeleteView(BaseAPIView):
    """Remove a verse from the fallback pool."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminVerseService()

    def delete(self, request: Request, verse_id: UUID) -> Response:
        self.service.delete_fallback_verse(verse_id=verse_id, admin_user=request.user)
        return self.no_content_response()


# ---------------------------------------------------------------------------
# Segregated Bible CMS
# ---------------------------------------------------------------------------


class AdminSectionListView(BaseAPIView):
    """List all bible sections or create a new one."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminBibleService()

    def get(self, request: Request) -> Response:
        sections = self.service.list_sections()
        serializer = AdminSectionSerializer(sections, many=True)
        return self.success_response(data=serializer.data, message="Sections retrieved")

    def post(self, request: Request) -> Response:
        serializer = AdminSectionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        section = self.service.create_section(
            **data,
            admin_user=request.user,
        )
        return self.created_response(
            data=AdminSectionSerializer(section).data,
            message="Section created",
        )


class AdminSectionDetailView(BaseAPIView):
    """Update or delete a bible section."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminBibleService()

    def put(self, request: Request, section_id: UUID) -> Response:
        serializer = AdminSectionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        section = self.service.update_section(
            section_id=section_id,
            **data,
            admin_user=request.user,
        )
        return self.success_response(
            data=AdminSectionSerializer(section).data,
            message="Section updated",
        )

    def delete(self, request: Request, section_id: UUID) -> Response:
        self.service.delete_section(section_id=section_id, admin_user=request.user)
        return self.no_content_response()


class AdminChapterListView(BaseAPIView):
    """List chapters belonging to a section or create a new chapter."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminBibleService()

    def get(self, request: Request, section_id: UUID) -> Response:
        chapters = self.service.list_chapters(section_id=section_id)
        serializer = AdminChapterSerializer(chapters, many=True)
        return self.success_response(data=serializer.data, message="Chapters retrieved")

    def post(self, request: Request, section_id: UUID) -> Response:
        serializer = AdminChapterCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        chapter = self.service.create_chapter(
            section_id=section_id,
            **data,
            admin_user=request.user,
        )
        return self.created_response(
            data=AdminChapterSerializer(chapter).data,
            message="Chapter created",
        )


class AdminChapterDetailView(BaseAPIView):
    """Update or delete a single chapter."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminBibleService()

    def put(self, request: Request, chapter_id: UUID) -> Response:
        serializer = AdminChapterUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        chapter = self.service.update_chapter(
            chapter_id=chapter_id,
            **data,
            admin_user=request.user,
        )
        return self.success_response(
            data=AdminChapterSerializer(chapter).data,
            message="Chapter updated",
        )

    def delete(self, request: Request, chapter_id: UUID) -> Response:
        self.service.delete_chapter(chapter_id=chapter_id, admin_user=request.user)
        return self.no_content_response()


class AdminChapterReorderView(BaseAPIView):
    """Reorder chapters within a section."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminBibleService()

    def post(self, request: Request, section_id: UUID) -> Response:
        serializer = AdminChapterReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        chapters = self.service.reorder_chapters(
            section_id=section_id,
            **data,
            admin_user=request.user,
        )
        return self.success_response(
            data=AdminChapterSerializer(chapters, many=True).data,
            message="Chapters reordered",
        )


class AdminPageListView(BaseAPIView):
    """List pages within a chapter or create a new page."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminBibleService()

    def get(self, request: Request, chapter_id: UUID) -> Response:
        pages = self.service.list_pages(chapter_id=chapter_id)
        serializer = AdminPageSerializer(pages, many=True)
        return self.success_response(data=serializer.data, message="Pages retrieved")

    def post(self, request: Request, chapter_id: UUID) -> Response:
        serializer = AdminPageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        page = self.service.create_page(
            chapter_id=chapter_id,
            **data,
            admin_user=request.user,
        )
        return self.created_response(
            data=AdminPageSerializer(page).data,
            message="Page created",
        )


class AdminPageDetailView(BaseAPIView):
    """Retrieve, update, or delete a single page."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminBibleService()

    def get(self, request: Request, page_id: UUID) -> Response:
        page = self.service.get_page_detail(page_id=page_id)
        serializer = AdminPageSerializer(page)
        return self.success_response(data=serializer.data, message="Page detail retrieved")

    def put(self, request: Request, page_id: UUID) -> Response:
        serializer = AdminPageUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        page = self.service.update_page(
            page_id=page_id,
            **data,
            admin_user=request.user,
        )
        return self.success_response(
            data=AdminPageSerializer(page).data,
            message="Page updated",
        )

    def delete(self, request: Request, page_id: UUID) -> Response:
        self.service.delete_page(page_id=page_id, admin_user=request.user)
        return self.no_content_response()


# ---------------------------------------------------------------------------
# Shop Management
# ---------------------------------------------------------------------------


class AdminProductListView(BaseAPIView):
    """Paginated list of products with optional filters; also handles creation."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminShopService()
        self.paginator = StandardPageNumberPagination()

    def get(self, request: Request) -> Response:
        queryset = self.service.list_products(
            category=request.query_params.get("category"),
            is_active=request.query_params.get("is_active"),
        )
        page = self.paginator.paginate_queryset(queryset, request, view=self)
        serializer = AdminProductSerializer(page, many=True)
        return self.paginator.get_paginated_response(serializer.data)

    def post(self, request: Request) -> Response:
        serializer = AdminProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        product = self.service.create_product(
            **data,
            admin_user=request.user,
        )
        return self.created_response(
            data=AdminProductSerializer(product).data,
            message="Product created",
        )


class AdminProductDetailView(BaseAPIView):
    """Retrieve, update, or delete a single product."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminShopService()

    def get(self, request: Request, product_id: UUID) -> Response:
        product = self.service.get_product_detail(product_id=product_id)
        serializer = AdminProductSerializer(product)
        return self.success_response(data=serializer.data, message="Product detail retrieved")

    def put(self, request: Request, product_id: UUID) -> Response:
        serializer = AdminProductUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        product = self.service.update_product(
            product_id=product_id,
            **data,
            admin_user=request.user,
        )
        return self.success_response(
            data=AdminProductSerializer(product).data,
            message="Product updated",
        )

    def delete(self, request: Request, product_id: UUID) -> Response:
        self.service.delete_product(product_id=product_id, admin_user=request.user)
        return self.no_content_response()


class AdminProductToggleView(BaseAPIView):
    """Toggle the active state of a product."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminShopService()

    def post(self, request: Request, product_id: UUID) -> Response:
        product = self.service.toggle_product_active(
            product_id=product_id,
            admin_user=request.user,
        )
        return self.success_response(
            data=AdminProductSerializer(product).data,
            message="Product active status toggled",
        )


class AdminProductStatsView(BaseAPIView):
    """Return purchase / download statistics for a product."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminShopService()

    def get(self, request: Request, product_id: UUID) -> Response:
        stats: dict[str, Any] = self.service.get_product_stats(product_id=product_id)
        serializer = AdminProductStatsSerializer(stats)
        return self.success_response(data=serializer.data, message="Product stats retrieved")


class AdminPurchaseListView(BaseAPIView):
    """Paginated list of purchases with optional filters."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminShopService()
        self.paginator = StandardPageNumberPagination()

    def get(self, request: Request) -> Response:
        queryset = self.service.list_purchases(
            product_id=request.query_params.get("product_id"),
            user_id=request.query_params.get("user_id"),
        )
        page = self.paginator.paginate_queryset(queryset, request, view=self)
        serializer = AdminPurchaseSerializer(page, many=True)
        return self.paginator.get_paginated_response(serializer.data)


# ---------------------------------------------------------------------------
# Boost Management
# ---------------------------------------------------------------------------


class AdminBoostListView(BaseAPIView):
    """Paginated list of boosts with optional filters."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminBoostService()
        self.paginator = StandardPageNumberPagination()

    def get(self, request: Request) -> Response:
        queryset = self.service.list_boosts(
            is_active=request.query_params.get("is_active"),
            user_id=request.query_params.get("user_id"),
        )
        page = self.paginator.paginate_queryset(queryset, request, view=self)
        serializer = AdminBoostSerializer(page, many=True)
        return self.paginator.get_paginated_response(serializer.data)


class AdminBoostDetailView(BaseAPIView):
    """Retrieve a boost along with its analytics snapshots."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminBoostService()

    def get(self, request: Request, boost_id: UUID) -> Response:
        boost = self.service.get_boost_detail(boost_id=boost_id)
        boost_data: dict[str, Any] = AdminBoostSerializer(boost).data
        snapshots = self.service.get_boost_snapshots(boost_id=boost_id)
        boost_data["snapshots"] = AdminBoostSnapshotSerializer(snapshots, many=True).data
        return self.success_response(data=boost_data, message="Boost detail retrieved")


class AdminBoostTierListView(BaseAPIView):
    """List all boost tiers or create a new one."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminBoostService()

    def get(self, request: Request) -> Response:
        tiers = self.service.list_boost_tiers()
        serializer = AdminBoostTierSerializer(tiers, many=True)
        return self.success_response(data=serializer.data, message="Boost tiers retrieved")

    def post(self, request: Request) -> Response:
        serializer = AdminBoostTierCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        tier = self.service.create_boost_tier(
            **data,
            admin_user=request.user,
        )
        return self.created_response(
            data=AdminBoostTierSerializer(tier).data,
            message="Boost tier created",
        )


class AdminBoostTierDetailView(BaseAPIView):
    """Update or delete a boost tier."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminBoostService()

    def put(self, request: Request, tier_id: UUID) -> Response:
        serializer = AdminBoostTierUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        tier = self.service.update_boost_tier(
            tier_id=tier_id,
            **data,
            admin_user=request.user,
        )
        return self.success_response(
            data=AdminBoostTierSerializer(tier).data,
            message="Boost tier updated",
        )

    def delete(self, request: Request, tier_id: UUID) -> Response:
        self.service.delete_boost_tier(tier_id=tier_id, admin_user=request.user)
        return self.no_content_response()


class AdminBoostRevenueView(BaseAPIView):
    """Return aggregated revenue statistics for boosts."""

    permission_classes: list[type[BasePermission]] = [IsContentAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminBoostService()

    def get(self, request: Request) -> Response:
        stats: dict[str, Any] = self.service.get_boost_revenue_stats()
        serializer = AdminBoostRevenueSerializer(stats)
        return self.success_response(data=serializer.data, message="Boost revenue retrieved")


# ---------------------------------------------------------------------------
# Broadcasts
# ---------------------------------------------------------------------------


class AdminBroadcastListView(BaseAPIView):
    """List all sent broadcasts."""

    permission_classes: list[type[BasePermission]] = [IsAdminStaff]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminBroadcastService()

    def get(self, request: Request) -> Response:
        broadcasts = self.service.list_broadcasts()
        serializer = AdminBroadcastSerializer(broadcasts, many=True)
        return self.success_response(data=serializer.data, message="Broadcasts retrieved")


class AdminBroadcastCreateView(BaseAPIView):
    """Send a new broadcast notification to users."""

    permission_classes: list[type[BasePermission]] = [IsAdminStaff]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminBroadcastService()

    def post(self, request: Request) -> Response:
        serializer = AdminBroadcastCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("admin_user", None)
        broadcast = self.service.send_broadcast(
            **data,
            admin_user=request.user,
        )
        return self.created_response(
            data=AdminBroadcastSerializer(broadcast).data,
            message="Broadcast sent",
        )


class AdminBroadcastDetailView(BaseAPIView):
    """Retrieve details of a single broadcast."""

    permission_classes: list[type[BasePermission]] = [IsAdminStaff]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminBroadcastService()

    def get(self, request: Request, notification_id: UUID) -> Response:
        detail = self.service.get_broadcast_detail(notification_id=notification_id)
        notification = detail["notification"]
        serializer = AdminBroadcastSerializer(notification)
        data = serializer.data
        data["total_sent"] = detail["total_sent"]
        data["total_read"] = detail["total_read"]
        data["read_rate"] = detail["read_rate"]
        return self.success_response(data=data, message="Broadcast detail retrieved")


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class AdminUserDemographicsView(BaseAPIView):
    """Return user demographic breakdowns."""

    permission_classes: list[type[BasePermission]] = [IsAdminStaff]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminAnalyticsService()

    def get(self, request: Request) -> Response:
        data: dict[str, Any] = self.service.get_user_demographics()
        serializer = AdminDemographicsSerializer(data)
        return self.success_response(data=serializer.data, message="Demographics retrieved")


class AdminContentEngagementView(BaseAPIView):
    """Return content engagement metrics over a configurable window."""

    permission_classes: list[type[BasePermission]] = [IsAdminStaff]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminAnalyticsService()

    def get(self, request: Request) -> Response:
        try:
            days: int = int(request.query_params.get("days", 30))
        except (TypeError, ValueError):
            days = 30
        data: dict[str, Any] = self.service.get_content_engagement(days=days)
        serializer = AdminContentEngagementSerializer(data)
        return self.success_response(data=serializer.data, message="Content engagement retrieved")


class AdminShopRevenueView(BaseAPIView):
    """Return shop revenue analytics over a configurable window."""

    permission_classes: list[type[BasePermission]] = [IsAdminStaff]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminAnalyticsService()

    def get(self, request: Request) -> Response:
        try:
            days: int = int(request.query_params.get("days", 30))
        except (TypeError, ValueError):
            days = 30
        data: dict[str, Any] = self.service.get_shop_revenue(days=days)
        serializer = AdminShopRevenueSerializer(data)
        return self.success_response(data=serializer.data, message="Shop revenue retrieved")


class AdminBoostPerformanceView(BaseAPIView):
    """Return boost performance metrics."""

    permission_classes: list[type[BasePermission]] = [IsAdminStaff]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminAnalyticsService()

    def get(self, request: Request) -> Response:
        data: dict[str, Any] = self.service.get_boost_performance()
        serializer = AdminBoostRevenueSerializer(data)
        return self.success_response(data=serializer.data, message="Boost performance retrieved")


# ---------------------------------------------------------------------------
# Admin Logs
# ---------------------------------------------------------------------------


class AdminLogListView(BaseAPIView):
    """Paginated list of admin audit log entries."""

    permission_classes: list[type[BasePermission]] = [IsSuperAdmin]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = AdminLogService()
        self.paginator = StandardPageNumberPagination()

    def get(self, request: Request) -> Response:
        queryset = self.service.get_logs(
            admin_user_id=request.query_params.get("admin_user_id"),
            action=request.query_params.get("action"),
            target_model=request.query_params.get("target_model"),
        )
        page = self.paginator.paginate_queryset(queryset, request, view=self)
        serializer = AdminLogSerializer(page, many=True)
        return self.paginator.get_paginated_response(serializer.data)
