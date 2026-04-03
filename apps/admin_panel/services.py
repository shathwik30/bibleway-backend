from __future__ import annotations
import datetime
from typing import Any
from uuid import UUID
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import (
    Avg,
    Count,
    F,
    Q,
    QuerySet,
    Sum,
)

from django.db.models.functions import TruncDate
from django.utils import timezone
from apps.accounts.models import FollowRelationship, User
from apps.admin_panel.models import AdminLog, AdminRole, BoostTier
from apps.analytics.models import BoostAnalyticSnapshot, PostBoost, PostView
from apps.bible.models import (
    SegregatedChapter,
    SegregatedPage,
    SegregatedPageComment,
    SegregatedSection,
    TranslatedPageCache,
)

from apps.notifications.models import Notification
from apps.shop.models import Download, Product, Purchase
from apps.social.models import Comment, Post, Prayer, Report
from apps.verse_of_day.models import VerseFallbackPool, VerseOfDay

_NON_MODEL_FIELDS = frozenset({"admin_user"})


def _clean_update_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Remove non-model fields from kwargs before applying to a model instance."""

    return {k: v for k, v in kwargs.items() if k not in _NON_MODEL_FIELDS}


def _subtract_years(d: datetime.date, years: int) -> datetime.date:
    """Subtract *years* from *d*, handling Feb 29 → Feb 28 gracefully."""

    try:
        return d.replace(year=d.year - years)

    except ValueError:
        return d.replace(year=d.year - years, month=2, day=28)


class AdminLogService:
    """Audit-trail service -- every admin write action is logged here."""

    @staticmethod
    def log_action(
        admin_user: User,
        action: str,
        target_model: str,
        target_id: str | UUID,
        detail: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AdminLog:
        """Create an ``AdminLog`` entry for an admin write action."""

        return AdminLog.objects.create(
            admin_user=admin_user,
            action=action,
            target_model=target_model,
            target_id=str(target_id),
            detail=detail,
            metadata=metadata or {},
        )

    @staticmethod
    def get_logs(
        admin_user_id: UUID | None = None,
        action: str | None = None,
        target_model: str | None = None,
    ) -> QuerySet[AdminLog]:
        """Return a filtered queryset of admin log entries."""
        qs: QuerySet[AdminLog] = AdminLog.objects.select_related("admin_user")

        if admin_user_id is not None:
            qs = qs.filter(admin_user_id=admin_user_id)

        if action is not None:
            qs = qs.filter(action=action)

        if target_model is not None:
            qs = qs.filter(target_model=target_model)

        return qs

    @staticmethod
    def get_recent_logs(limit: int = 50) -> QuerySet[AdminLog]:
        """Return the *limit* most-recent admin log entries."""

        return AdminLog.objects.select_related("admin_user").order_by("-created_at")[
            :limit
        ]


class AdminDashboardService:
    """High-level statistics for the admin dashboard overview page."""

    @staticmethod
    def get_overview() -> dict[str, Any]:
        """Aggregate key platform metrics into a single dict."""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - datetime.timedelta(days=7)

        return {
            "total_users": User.objects.count(),
            "daily_active_users": User.objects.filter(
                last_login__gte=now - datetime.timedelta(hours=24),
            ).count(),
            "new_signups_today": User.objects.filter(
                date_joined__gte=today_start,
            ).count(),
            "new_signups_week": User.objects.filter(
                date_joined__gte=week_ago,
            ).count(),
            "total_posts": Post.objects.count(),
            "total_prayers": Prayer.objects.count(),
            "active_boosts_count": PostBoost.objects.filter(
                is_active=True,
            ).count(),
            "total_purchases": Purchase.objects.count(),
            "total_downloads": Download.objects.count(),
        }

    @staticmethod
    def get_user_growth_data(days: int = 30) -> list[dict[str, Any]]:
        """Return daily new-signup counts for the last *days* days.
        Returns a list of ``{"date": <date>, "count": <int>}`` dicts suitable
        for charting.
        """
        since = timezone.now() - datetime.timedelta(days=days)
        rows = (
            User.objects.filter(date_joined__gte=since)
            .annotate(date=TruncDate("date_joined"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        return [{"date": row["date"], "count": row["count"]} for row in rows]

    @staticmethod
    def get_content_stats() -> dict[str, int]:
        """Return total counts for posts, prayers, and comments."""

        return {
            "posts": Post.objects.count(),
            "prayers": Prayer.objects.count(),
            "comments": Comment.objects.count(),
        }


class AdminUserService:
    """CRUD and management operations on user accounts."""

    @staticmethod
    def list_users(
        search: str | None = None,
        country: str | None = None,
        is_active: bool | None = None,
        ordering: str = "-date_joined",
    ) -> QuerySet[User]:
        """Return a filtered, ordered queryset of users."""
        qs: QuerySet[User] = User.objects.all()

        if search:
            qs = qs.filter(
                Q(email__icontains=search) | Q(full_name__icontains=search),
            )

        if country is not None:
            qs = qs.filter(country=country)

        if is_active is not None:
            qs = qs.filter(is_active=is_active)

        return qs.order_by(ordering)

    @staticmethod
    def get_user_detail(user_id: UUID) -> dict[str, Any]:
        """Return a user together with aggregated relationship counts."""
        user: User = User.objects.get(pk=user_id)

        return {
            "user": user,
            "posts_count": Post.objects.filter(author=user).count(),
            "prayers_count": Prayer.objects.filter(author=user).count(),
            "followers_count": FollowRelationship.objects.filter(
                following=user,
            ).count(),
            "following_count": FollowRelationship.objects.filter(
                follower=user,
            ).count(),
        }

    @staticmethod
    @transaction.atomic
    def suspend_user(
        admin_user: User,
        user_id: UUID,
        reason: str = "",
    ) -> User:
        """Deactivate a user account and log the action."""
        user: User = User.objects.select_for_update().get(pk=user_id)
        user.is_active = False
        user.save(update_fields=["is_active"])
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.SUSPEND,
            target_model="accounts.User",
            target_id=user_id,
            detail=reason,
        )

        return user

    @staticmethod
    @transaction.atomic
    def unsuspend_user(admin_user: User, user_id: UUID) -> User:
        """Re-activate a suspended user account and log the action."""
        user: User = User.objects.select_for_update().get(pk=user_id)
        user.is_active = True
        user.save(update_fields=["is_active"])
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.UNSUSPEND,
            target_model="accounts.User",
            target_id=user_id,
            detail=f"User {user.email} unsuspended.",
        )

        return user

    @staticmethod
    @transaction.atomic
    def create_admin_user(
        admin_user: User,
        email: str,
        password: str,
        full_name: str,
        role: str,
    ) -> User:
        """Create a new staff user with an ``AdminRole`` and log the action."""
        new_user: User = User.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            is_staff=True,
            is_active=True,
            is_email_verified=True,
            date_of_birth=datetime.date(2000, 1, 1),
            gender=User.Gender.PREFER_NOT_TO_SAY,
            country="",
        )
        AdminRole.objects.create(user=new_user, role=role)
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.CREATE,
            target_model="accounts.User",
            target_id=new_user.pk,
            detail=f"Admin user created: {email} with role {role}.",
            metadata={"role": role},
        )

        return new_user

    @staticmethod
    @transaction.atomic
    def update_admin_role(
        admin_user: User,
        target_user_id: UUID,
        new_role: str,
    ) -> AdminRole:
        """Change the admin role of an existing staff user."""
        admin_role: AdminRole = AdminRole.objects.select_for_update().get(
            user_id=target_user_id,
        )
        old_role: str = admin_role.role
        admin_role.role = new_role
        admin_role.save(update_fields=["role"])
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.ROLE_CHANGE,
            target_model="admin_panel.AdminRole",
            target_id=target_user_id,
            detail=f"Role changed from {old_role} to {new_role}.",
            metadata={"old_role": old_role, "new_role": new_role},
        )

        return admin_role

    @staticmethod
    def list_admin_users() -> QuerySet[User]:
        """Return all staff users with their admin roles eagerly loaded."""

        return User.objects.filter(is_staff=True).select_related("admin_role")

    @staticmethod
    @transaction.atomic
    def delete_admin_user(admin_user: User, target_user_id: UUID) -> None:
        """Remove staff privileges and the ``AdminRole`` from a user."""
        target_user: User = User.objects.select_for_update().get(
            pk=target_user_id,
        )
        AdminRole.objects.filter(user=target_user).delete()
        target_user.is_staff = False
        target_user.save(update_fields=["is_staff"])
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.DELETE,
            target_model="admin_panel.AdminRole",
            target_id=target_user_id,
            detail=f"Admin privileges removed from {target_user.email}.",
        )


class AdminModerationService:
    """Report review, content removal, user warnings, and suspensions."""

    @staticmethod
    def list_reports(
        status: str | None = None,
        content_type: str | None = None,
    ) -> QuerySet[Report]:
        """Return a filtered queryset of reports.
        ``content_type`` accepts a model name string such as ``"post"`` or
        ``"prayer"``.
        """
        qs: QuerySet[Report] = Report.objects.select_related(
            "reporter",
            "reviewed_by",
            "content_type",
        )

        if status is not None:
            qs = qs.filter(status=status)

        if content_type is not None:
            ct = ContentType.objects.get(model=content_type)
            qs = qs.filter(content_type=ct)

        return qs

    @staticmethod
    def get_report_detail(report_id: UUID) -> Report:
        """Return a single report with all related objects."""

        return Report.objects.select_related(
            "reporter",
            "reviewed_by",
            "content_type",
        ).get(pk=report_id)

    @staticmethod
    @transaction.atomic
    def dismiss_report(admin_user: User, report_id: UUID) -> Report:
        """Mark a report as dismissed without taking further action."""
        report: Report = Report.objects.select_for_update().get(pk=report_id)
        report.status = Report.Status.DISMISSED
        report.reviewed_by = admin_user
        report.reviewed_at = timezone.now()
        report.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.DISMISS_REPORT,
            target_model="social.Report",
            target_id=report_id,
            detail=f"Report {report_id} dismissed.",
        )

        return report

    @staticmethod
    @transaction.atomic
    def remove_content(admin_user: User, report_id: UUID) -> Report:
        """Delete the reported content object and mark the report reviewed."""
        report: Report = Report.objects.select_for_update().get(pk=report_id)
        content_object = report.content_object
        target_model_label: str = (
            f"{report.content_type.app_label}.{report.content_type.model}"
        )
        target_id: str = str(report.object_id)

        if content_object is not None:
            content_object.delete()

        report.status = Report.Status.REVIEWED
        report.reviewed_by = admin_user
        report.reviewed_at = timezone.now()
        report.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.REMOVE_CONTENT,
            target_model=target_model_label,
            target_id=target_id,
            detail=f"Content removed via report {report_id}.",
        )

        return report

    @staticmethod
    @transaction.atomic
    def warn_user(
        admin_user: User,
        report_id: UUID,
        warning_message: str,
    ) -> Report:
        """Send a warning notification to the owner of reported content."""
        report: Report = Report.objects.select_for_update().get(pk=report_id)
        content_object = report.content_object

        if hasattr(content_object, "author"):
            reported_user: User = content_object.author

        elif hasattr(content_object, "user"):
            reported_user = content_object.user

        else:
            reported_user = content_object

        Notification.objects.create(
            recipient=reported_user,
            sender=None,
            notification_type=Notification.NotificationType.SYSTEM_BROADCAST,
            title="Warning from BibleWay Moderation",
            body=warning_message,
            data={"report_id": str(report_id)},
        )
        report.status = Report.Status.REVIEWED
        report.reviewed_by = admin_user
        report.reviewed_at = timezone.now()
        report.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.WARN,
            target_model="accounts.User",
            target_id=reported_user.pk,
            detail=f"Warning issued via report {report_id}: {warning_message}",
            metadata={"report_id": str(report_id)},
        )

        return report

    @staticmethod
    @transaction.atomic
    def suspend_from_report(admin_user: User, report_id: UUID) -> Report:
        """Suspend the user who owns the reported content."""
        report: Report = Report.objects.select_for_update().get(pk=report_id)
        content_object = report.content_object

        if hasattr(content_object, "author"):
            reported_user: User = content_object.author

        elif hasattr(content_object, "user"):
            reported_user = content_object.user

        else:
            reported_user = content_object

        AdminUserService.suspend_user(
            admin_user=admin_user,
            user_id=reported_user.pk,
            reason=f"Suspended via report {report_id}.",
        )
        report.status = Report.Status.REVIEWED
        report.reviewed_by = admin_user
        report.reviewed_at = timezone.now()
        report.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        return report

    @staticmethod
    def get_reports_for_user(user_id: UUID) -> QuerySet[Report]:
        """Return all reports where the given user is the *reported* party.
        This looks up reports whose generic-FK points at content authored by
        the user, as well as reports that point directly at the user object.
        """
        user_ct = ContentType.objects.get_for_model(User)
        direct_q = Q(content_type=user_ct, object_id=user_id)
        post_ids = Post.objects.filter(author_id=user_id).values_list(
            "id",
            flat=True,
        )
        prayer_ids = Prayer.objects.filter(author_id=user_id).values_list(
            "id",
            flat=True,
        )
        comment_ids = Comment.objects.filter(user_id=user_id).values_list(
            "id",
            flat=True,
        )
        post_ct = ContentType.objects.get_for_model(Post)
        prayer_ct = ContentType.objects.get_for_model(Prayer)
        comment_ct = ContentType.objects.get_for_model(Comment)
        content_q = (
            Q(content_type=post_ct, object_id__in=post_ids)
            | Q(content_type=prayer_ct, object_id__in=prayer_ids)
            | Q(content_type=comment_ct, object_id__in=comment_ids)
        )

        return Report.objects.filter(direct_q | content_q).select_related(
            "reporter",
            "reviewed_by",
            "content_type",
        )


class AdminVerseService:
    """Verse of the Day and fallback pool management."""

    @staticmethod
    def list_verses(scheduled_only: bool = False) -> QuerySet[VerseOfDay]:
        """Return all verses, optionally filtering to future-scheduled ones."""
        qs: QuerySet[VerseOfDay] = VerseOfDay.objects.all()

        if scheduled_only:
            qs = qs.filter(display_date__gte=timezone.now().date())

        return qs

    @staticmethod
    @transaction.atomic
    def create_verse(
        admin_user: User,
        bible_reference: str,
        verse_text: str,
        display_date: datetime.date,
        background_image: Any | None = None,
    ) -> VerseOfDay:
        """Create a new Verse of the Day and log the action."""
        verse = VerseOfDay.objects.create(
            bible_reference=bible_reference,
            verse_text=verse_text,
            display_date=display_date,
            background_image=background_image or "",
        )
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.CREATE,
            target_model="verse_of_day.VerseOfDay",
            target_id=verse.pk,
            detail=f"Verse created: {bible_reference} for {display_date}.",
        )

        return verse

    @staticmethod
    @transaction.atomic
    def update_verse(
        admin_user: User,
        verse_id: UUID,
        **kwargs: Any,
    ) -> VerseOfDay:
        """Update an existing Verse of the Day and log the action."""
        clean_kwargs = _clean_update_kwargs(kwargs)
        verse: VerseOfDay = VerseOfDay.objects.select_for_update().get(
            pk=verse_id,
        )
        changed_fields: list[str] = []

        for field, value in clean_kwargs.items():
            setattr(verse, field, value)
            changed_fields.append(field)

        if changed_fields:
            if "updated_at" not in changed_fields and hasattr(verse, "updated_at"):
                changed_fields.append("updated_at")

            verse.save(update_fields=changed_fields)

        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.UPDATE,
            target_model="verse_of_day.VerseOfDay",
            target_id=verse_id,
            detail=f"Updated fields: {', '.join(changed_fields)}.",
            metadata={"changed_fields": changed_fields},
        )

        return verse

    @staticmethod
    @transaction.atomic
    def delete_verse(admin_user: User, verse_id: UUID) -> None:
        """Delete a Verse of the Day and log the action."""
        verse: VerseOfDay = VerseOfDay.objects.get(pk=verse_id)
        reference: str = verse.bible_reference
        verse.delete()
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.DELETE,
            target_model="verse_of_day.VerseOfDay",
            target_id=verse_id,
            detail=f"Verse deleted: {reference}.",
        )

    @staticmethod
    def list_fallback_pool() -> QuerySet[VerseFallbackPool]:
        """Return all entries in the fallback pool."""

        return VerseFallbackPool.objects.all()

    @staticmethod
    @transaction.atomic
    def create_fallback_verse(
        admin_user: User,
        bible_reference: str,
        verse_text: str,
        background_image: Any | None = None,
    ) -> VerseFallbackPool:
        """Create a new fallback verse and log the action."""
        verse = VerseFallbackPool.objects.create(
            bible_reference=bible_reference,
            verse_text=verse_text,
            background_image=background_image or "",
        )
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.CREATE,
            target_model="verse_of_day.VerseFallbackPool",
            target_id=verse.pk,
            detail=f"Fallback verse created: {bible_reference}.",
        )

        return verse

    @staticmethod
    @transaction.atomic
    def update_fallback_verse(
        admin_user: User,
        verse_id: UUID,
        **kwargs: Any,
    ) -> VerseFallbackPool:
        """Update an existing fallback verse and log the action."""
        clean_kwargs = _clean_update_kwargs(kwargs)
        verse: VerseFallbackPool = VerseFallbackPool.objects.select_for_update().get(
            pk=verse_id
        )
        changed_fields: list[str] = []

        for field, value in clean_kwargs.items():
            setattr(verse, field, value)
            changed_fields.append(field)

        if changed_fields:
            if "updated_at" not in changed_fields and hasattr(verse, "updated_at"):
                changed_fields.append("updated_at")

            verse.save(update_fields=changed_fields)

        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.UPDATE,
            target_model="verse_of_day.VerseFallbackPool",
            target_id=verse_id,
            detail=f"Updated fields: {', '.join(changed_fields)}.",
            metadata={"changed_fields": changed_fields},
        )

        return verse

    @staticmethod
    @transaction.atomic
    def delete_fallback_verse(admin_user: User, verse_id: UUID) -> None:
        """Delete a fallback verse and log the action."""
        verse: VerseFallbackPool = VerseFallbackPool.objects.get(pk=verse_id)
        reference: str = verse.bible_reference
        verse.delete()
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.DELETE,
            target_model="verse_of_day.VerseFallbackPool",
            target_id=verse_id,
            detail=f"Fallback verse deleted: {reference}.",
        )

    @staticmethod
    @transaction.atomic
    def bulk_create_verses(
        admin_user: User,
        verses_data: list[dict[str, Any]],
    ) -> list[VerseOfDay]:
        """Bulk-create Verse of the Day entries and log the action.
        Each dict in *verses_data* must contain ``bible_reference``,
        ``verse_text``, and ``display_date``.  ``background_image`` is
        optional.
        """
        instances: list[VerseOfDay] = [
            VerseOfDay(
                bible_reference=v["bible_reference"],
                verse_text=v["verse_text"],
                display_date=v["display_date"],
                background_image=v.get("background_image", ""),
            )
            for v in verses_data
        ]
        created: list[VerseOfDay] = VerseOfDay.objects.bulk_create(instances)
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.CREATE,
            target_model="verse_of_day.VerseOfDay",
            target_id="bulk",
            detail=f"Bulk created {len(created)} verses.",
            metadata={
                "count": len(created),
                "ids": [str(v.pk) for v in created],
            },
        )

        return created


class AdminBibleService:
    """Segregated Bible content management (sections / chapters / pages)."""

    @staticmethod
    def list_sections() -> QuerySet[SegregatedSection]:
        """Return all segregated sections ordered by *order*."""

        return SegregatedSection.objects.all()

    @staticmethod
    @transaction.atomic
    def create_section(
        admin_user: User,
        title: str,
        age_min: int,
        age_max: int,
        order: int = 0,
    ) -> SegregatedSection:
        """Create a new segregated section and log the action."""
        section = SegregatedSection.objects.create(
            title=title,
            age_min=age_min,
            age_max=age_max,
            order=order,
        )
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.CREATE,
            target_model="bible.SegregatedSection",
            target_id=section.pk,
            detail=f"Section created: {title} (Ages {age_min}-{age_max}).",
        )

        return section

    @staticmethod
    @transaction.atomic
    def update_section(
        admin_user: User,
        section_id: UUID,
        **kwargs: Any,
    ) -> SegregatedSection:
        """Update a segregated section and log the action."""
        clean_kwargs = _clean_update_kwargs(kwargs)
        section: SegregatedSection = SegregatedSection.objects.select_for_update().get(
            pk=section_id
        )
        changed_fields: list[str] = []

        for field, value in clean_kwargs.items():
            setattr(section, field, value)
            changed_fields.append(field)

        if changed_fields:
            if "updated_at" not in changed_fields and hasattr(section, "updated_at"):
                changed_fields.append("updated_at")

            section.save(update_fields=changed_fields)

        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.UPDATE,
            target_model="bible.SegregatedSection",
            target_id=section_id,
            detail=f"Updated fields: {', '.join(changed_fields)}.",
            metadata={"changed_fields": changed_fields},
        )

        return section

    @staticmethod
    @transaction.atomic
    def delete_section(admin_user: User, section_id: UUID) -> None:
        """Delete a segregated section (cascading) and log the action."""
        section: SegregatedSection = SegregatedSection.objects.get(
            pk=section_id,
        )
        title: str = section.title
        section.delete()
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.DELETE,
            target_model="bible.SegregatedSection",
            target_id=section_id,
            detail=f"Section deleted: {title} (cascade).",
        )

    @staticmethod
    def list_chapters(section_id: UUID) -> QuerySet[SegregatedChapter]:
        """Return all chapters for a given section."""

        return SegregatedChapter.objects.filter(section_id=section_id)

    @staticmethod
    @transaction.atomic
    def create_chapter(
        admin_user: User,
        section_id: UUID,
        title: str,
        order: int = 0,
    ) -> SegregatedChapter:
        """Create a new chapter in the given section and log the action."""
        chapter = SegregatedChapter.objects.create(
            section_id=section_id,
            title=title,
            order=order,
        )
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.CREATE,
            target_model="bible.SegregatedChapter",
            target_id=chapter.pk,
            detail=f"Chapter created: {title} in section {section_id}.",
        )

        return chapter

    @staticmethod
    @transaction.atomic
    def update_chapter(
        admin_user: User,
        chapter_id: UUID,
        **kwargs: Any,
    ) -> SegregatedChapter:
        """Update a chapter and log the action."""
        clean_kwargs = _clean_update_kwargs(kwargs)
        chapter: SegregatedChapter = SegregatedChapter.objects.select_for_update().get(
            pk=chapter_id
        )
        changed_fields: list[str] = []

        for field, value in clean_kwargs.items():
            setattr(chapter, field, value)
            changed_fields.append(field)

        if changed_fields:
            if "updated_at" not in changed_fields and hasattr(chapter, "updated_at"):
                changed_fields.append("updated_at")

            chapter.save(update_fields=changed_fields)

        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.UPDATE,
            target_model="bible.SegregatedChapter",
            target_id=chapter_id,
            detail=f"Updated fields: {', '.join(changed_fields)}.",
            metadata={"changed_fields": changed_fields},
        )

        return chapter

    @staticmethod
    @transaction.atomic
    def delete_chapter(admin_user: User, chapter_id: UUID) -> None:
        """Delete a chapter (cascading) and log the action."""
        chapter: SegregatedChapter = SegregatedChapter.objects.get(
            pk=chapter_id,
        )
        title: str = chapter.title
        chapter.delete()
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.DELETE,
            target_model="bible.SegregatedChapter",
            target_id=chapter_id,
            detail=f"Chapter deleted: {title} (cascade).",
        )

    @staticmethod
    @transaction.atomic
    def reorder_chapters(
        admin_user: User,
        section_id: UUID,
        ordered_ids: list[UUID],
    ) -> QuerySet[SegregatedChapter]:
        """Bulk-update chapter order within a section.
        ``ordered_ids`` is a list of chapter UUIDs in the desired display
        order; the index becomes the new ``order`` value.
        Returns the updated queryset so callers can serialize the result.
        """
        chapters = SegregatedChapter.objects.filter(
            section_id=section_id,
            pk__in=ordered_ids,
        )
        chapter_map: dict[UUID, SegregatedChapter] = {c.pk: c for c in chapters}
        to_update: list[SegregatedChapter] = []

        for index, chapter_id in enumerate(ordered_ids):
            chapter = chapter_map.get(chapter_id)

            if chapter is not None:
                chapter.order = index
                to_update.append(chapter)

        SegregatedChapter.objects.bulk_update(to_update, ["order"])
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.UPDATE,
            target_model="bible.SegregatedChapter",
            target_id=str(section_id),
            detail=f"Reordered {len(to_update)} chapters in section {section_id}.",
            metadata={"ordered_ids": [str(uid) for uid in ordered_ids]},
        )

        return SegregatedChapter.objects.filter(
            section_id=section_id,
        ).order_by("order")

    @staticmethod
    def list_pages(chapter_id: UUID) -> QuerySet[SegregatedPage]:
        """Return all pages for a given chapter."""

        return SegregatedPage.objects.filter(chapter_id=chapter_id)

    @staticmethod
    def get_page_detail(page_id: UUID) -> SegregatedPage:
        """Return a single page by ID."""

        try:
            return SegregatedPage.objects.select_related(
                "chapter", "chapter__section"
            ).get(pk=page_id)

        except SegregatedPage.DoesNotExist:
            from apps.common.exceptions import NotFoundError

            raise NotFoundError(detail=f"Page with id '{page_id}' not found.")

    @staticmethod
    @transaction.atomic
    def create_page(
        admin_user: User,
        chapter_id: UUID,
        title: str,
        content: str,
        youtube_url: str = "",
        order: int = 0,
    ) -> SegregatedPage:
        """Create a new page in the given chapter and log the action."""
        page = SegregatedPage.objects.create(
            chapter_id=chapter_id,
            title=title,
            content=content,
            youtube_url=youtube_url,
            order=order,
        )
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.CREATE,
            target_model="bible.SegregatedPage",
            target_id=page.pk,
            detail=f"Page created: {title} in chapter {chapter_id}.",
        )

        return page

    @staticmethod
    @transaction.atomic
    def update_page(
        admin_user: User,
        page_id: UUID,
        **kwargs: Any,
    ) -> SegregatedPage:
        """Update a page and log the action.
        If the ``content`` field is changed, all cached translations for
        this page are invalidated.
        """
        clean_kwargs = _clean_update_kwargs(kwargs)
        page: SegregatedPage = SegregatedPage.objects.select_for_update().get(
            pk=page_id,
        )
        changed_fields: list[str] = []

        for field, value in clean_kwargs.items():
            setattr(page, field, value)
            changed_fields.append(field)

        if changed_fields:
            if "updated_at" not in changed_fields and hasattr(page, "updated_at"):
                changed_fields.append("updated_at")

            page.save(update_fields=changed_fields)

        if "content" in changed_fields:
            TranslatedPageCache.objects.filter(page=page).delete()

        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.UPDATE,
            target_model="bible.SegregatedPage",
            target_id=page_id,
            detail=f"Updated fields: {', '.join(changed_fields)}.",
            metadata={"changed_fields": changed_fields},
        )

        return page

    @staticmethod
    @transaction.atomic
    def delete_page(admin_user: User, page_id: UUID) -> None:
        """Delete a page and log the action."""
        page: SegregatedPage = SegregatedPage.objects.get(pk=page_id)
        title: str = page.title
        page.delete()
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.DELETE,
            target_model="bible.SegregatedPage",
            target_id=page_id,
            detail=f"Page deleted: {title}.",
        )

    @staticmethod
    def list_page_comments(
        page_id: UUID | None = None,
    ) -> QuerySet[SegregatedPageComment]:
        """Return page comments, optionally filtered by page."""
        qs: QuerySet[SegregatedPageComment] = (
            SegregatedPageComment.objects.select_related(
                "user",
                "page",
                "page__chapter",
                "page__chapter__section",
            ).order_by("-created_at")
        )

        if page_id is not None:
            qs = qs.filter(page_id=page_id)

        return qs

    @staticmethod
    @transaction.atomic
    def delete_page_comment(admin_user: User, comment_id: UUID) -> None:
        """Delete a page comment and log the action."""
        from apps.common.exceptions import NotFoundError

        try:
            comment: SegregatedPageComment = SegregatedPageComment.objects.get(
                pk=comment_id,
            )

        except SegregatedPageComment.DoesNotExist:
            raise NotFoundError(detail=f"Comment with id '{comment_id}' not found.")

        comment.delete()
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.DELETE,
            target_model="bible.SegregatedPageComment",
            target_id=comment_id,
            detail="Page comment deleted.",
        )

    @staticmethod
    def get_page_like_stats() -> list[dict[str, Any]]:
        """Return like counts per page with breadcrumb titles."""

        return list(
            SegregatedPage.objects.filter(
                likes__isnull=False,
            )
            .values("id", "title", "chapter__title", "chapter__section__title")
            .annotate(like_count=Count("likes"))
            .order_by("-like_count")
            .values(
                page_id=F("id"),
                page_title=F("title"),
                chapter_title=F("chapter__title"),
                section_title=F("chapter__section__title"),
                like_count=F("like_count"),
            )
        )


class AdminShopService:
    """Product catalogue and purchase management."""

    @staticmethod
    def list_products(
        category: str | None = None,
        is_active: bool | None = None,
    ) -> QuerySet[Product]:
        """Return a filtered product queryset."""
        qs: QuerySet[Product] = Product.objects.all()

        if category is not None:
            qs = qs.filter(category=category)

        if is_active is not None:
            qs = qs.filter(is_active=is_active)

        return qs

    @staticmethod
    def get_product_detail(product_id: UUID) -> Product:
        """Return a single product by ID."""

        try:
            return Product.objects.get(pk=product_id)

        except Product.DoesNotExist:
            from apps.common.exceptions import NotFoundError

            raise NotFoundError(detail=f"Product with id '{product_id}' not found.")

    @staticmethod
    @transaction.atomic
    def create_product(
        admin_user: User,
        title: str,
        description: str,
        cover_image: Any,
        product_file: Any,
        category: str,
        is_free: bool,
        price_tier: str = "",
        apple_product_id: str = "",
        google_product_id: str = "",
    ) -> Product:
        """Create a new shop product and log the action."""
        product = Product.objects.create(
            title=title,
            description=description,
            cover_image=cover_image,
            product_file=product_file,
            category=category,
            is_free=is_free,
            price_tier=price_tier,
            apple_product_id=apple_product_id,
            google_product_id=google_product_id,
        )
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.CREATE,
            target_model="shop.Product",
            target_id=product.pk,
            detail=f"Product created: {title}.",
        )

        return product

    @staticmethod
    @transaction.atomic
    def update_product(
        admin_user: User,
        product_id: UUID,
        **kwargs: Any,
    ) -> Product:
        """Update an existing product and log the action."""
        clean_kwargs = _clean_update_kwargs(kwargs)
        product: Product = Product.objects.select_for_update().get(
            pk=product_id,
        )
        changed_fields: list[str] = []

        for field, value in clean_kwargs.items():
            setattr(product, field, value)
            changed_fields.append(field)

        if changed_fields:
            if "updated_at" not in changed_fields and hasattr(product, "updated_at"):
                changed_fields.append("updated_at")

            product.save(update_fields=changed_fields)

        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.UPDATE,
            target_model="shop.Product",
            target_id=product_id,
            detail=f"Updated fields: {', '.join(changed_fields)}.",
            metadata={"changed_fields": changed_fields},
        )

        return product

    @staticmethod
    @transaction.atomic
    def delete_product(admin_user: User, product_id: UUID) -> None:
        """Delete a product and log the action."""
        product: Product = Product.objects.get(pk=product_id)
        title: str = product.title
        product.delete()
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.DELETE,
            target_model="shop.Product",
            target_id=product_id,
            detail=f"Product deleted: {title}.",
        )

    @staticmethod
    @transaction.atomic
    def toggle_product_active(admin_user: User, product_id: UUID) -> Product:
        """Toggle the ``is_active`` flag on a product and log the action."""
        product: Product = Product.objects.select_for_update().get(
            pk=product_id,
        )
        product.is_active = not product.is_active
        product.save(update_fields=["is_active", "updated_at"])
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.UPDATE,
            target_model="shop.Product",
            target_id=product_id,
            detail=f"Product {'activated' if product.is_active else 'deactivated'}: {product.title}.",
        )

        return product

    @staticmethod
    def get_product_stats(product_id: UUID) -> dict[str, int]:
        """Return purchase and download counts for a single product."""

        return {
            "purchase_count": Purchase.objects.filter(
                product_id=product_id,
            ).count(),
            "download_count": Download.objects.filter(
                product_id=product_id,
            ).count(),
        }

    @staticmethod
    def list_purchases(
        product_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> QuerySet[Purchase]:
        """Return a filtered purchase queryset."""
        qs: QuerySet[Purchase] = Purchase.objects.select_related(
            "user",
            "product",
        )

        if product_id is not None:
            qs = qs.filter(product_id=product_id)

        if user_id is not None:
            qs = qs.filter(user_id=user_id)

        return qs


class AdminBoostService:
    """Post-boost and boost-tier management."""

    @staticmethod
    def list_boosts(
        is_active: bool | None = None,
        user_id: UUID | None = None,
    ) -> QuerySet[PostBoost]:
        """Return a filtered PostBoost queryset with related objects."""
        qs: QuerySet[PostBoost] = PostBoost.objects.select_related(
            "post",
            "user",
        )

        if is_active is not None:
            qs = qs.filter(is_active=is_active)

        if user_id is not None:
            qs = qs.filter(user_id=user_id)

        return qs

    @staticmethod
    def get_boost_detail(boost_id: UUID) -> PostBoost:
        """Return a PostBoost with related objects."""

        try:
            return PostBoost.objects.select_related(
                "post",
                "user",
            ).get(pk=boost_id)

        except PostBoost.DoesNotExist:
            from apps.common.exceptions import NotFoundError

            raise NotFoundError(detail=f"Boost with id '{boost_id}' not found.")

    @staticmethod
    def get_boost_snapshots(boost_id: UUID) -> QuerySet[BoostAnalyticSnapshot]:
        """Return analytics snapshots for a specific boost."""

        return BoostAnalyticSnapshot.objects.filter(boost_id=boost_id).order_by(
            "-snapshot_date"
        )

    @staticmethod
    def list_boost_tiers() -> QuerySet[BoostTier]:
        """Return all boost tiers."""

        return BoostTier.objects.all()

    @staticmethod
    @transaction.atomic
    def create_boost_tier(
        admin_user: User,
        name: str,
        apple_product_id: str,
        google_product_id: str,
        duration_days: int,
        display_price: str,
    ) -> BoostTier:
        """Create a new boost tier and log the action."""
        tier = BoostTier.objects.create(
            name=name,
            apple_product_id=apple_product_id,
            google_product_id=google_product_id,
            duration_days=duration_days,
            display_price=display_price,
        )
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.CREATE,
            target_model="admin_panel.BoostTier",
            target_id=tier.pk,
            detail=f"Boost tier created: {name} ({duration_days} days, {display_price}).",
        )

        return tier

    @staticmethod
    @transaction.atomic
    def update_boost_tier(
        admin_user: User,
        tier_id: UUID,
        **kwargs: Any,
    ) -> BoostTier:
        """Update an existing boost tier and log the action."""
        clean_kwargs = _clean_update_kwargs(kwargs)
        tier: BoostTier = BoostTier.objects.select_for_update().get(
            pk=tier_id,
        )
        changed_fields: list[str] = []

        for field, value in clean_kwargs.items():
            setattr(tier, field, value)
            changed_fields.append(field)

        if changed_fields:
            if "updated_at" not in changed_fields and hasattr(tier, "updated_at"):
                changed_fields.append("updated_at")

            tier.save(update_fields=changed_fields)

        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.UPDATE,
            target_model="admin_panel.BoostTier",
            target_id=tier_id,
            detail=f"Updated fields: {', '.join(changed_fields)}.",
            metadata={"changed_fields": changed_fields},
        )

        return tier

    @staticmethod
    @transaction.atomic
    def delete_boost_tier(admin_user: User, tier_id: UUID) -> None:
        """Delete a boost tier and log the action."""
        tier: BoostTier = BoostTier.objects.get(pk=tier_id)
        name: str = tier.name
        tier.delete()
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.DELETE,
            target_model="admin_panel.BoostTier",
            target_id=tier_id,
            detail=f"Boost tier deleted: {name}.",
        )

    @staticmethod
    def get_boost_revenue_stats() -> dict[str, Any]:
        """Return aggregate boost metrics grouped by tier."""
        total_boosts: int = PostBoost.objects.count()
        active_boosts: int = PostBoost.objects.filter(is_active=True).count()
        revenue_by_tier = (
            PostBoost.objects.values("tier")
            .annotate(
                count=Count("id"),
                active_count=Count("id", filter=Q(is_active=True)),
                avg_duration=Avg("duration_days"),
            )
            .order_by("tier")
        )

        return {
            "total_boosts": total_boosts,
            "active_boosts": active_boosts,
            "revenue_by_tier": list(revenue_by_tier),
        }


class AdminBroadcastService:
    """System-wide broadcast notification management."""

    @staticmethod
    @transaction.atomic
    def send_broadcast(
        admin_user: User,
        title: str,
        body: str,
        filters: dict[str, Any] | None = None,
    ) -> list[Notification]:
        """Create a broadcast notification for all users matching filters.
        ``filters`` may contain: ``country``, ``language``,
        ``age_min``, ``age_max``.
        """
        _ALLOWED_FILTER_KEYS = {"country", "language", "age_min", "age_max"}
        segment_filters = {
            k: v for k, v in (filters or {}).items() if k in _ALLOWED_FILTER_KEYS
        }
        user_qs: QuerySet[User] = User.objects.filter(is_active=True)

        if "country" in segment_filters:
            user_qs = user_qs.filter(country=segment_filters["country"])

        if "language" in segment_filters:
            user_qs = user_qs.filter(preferred_language=segment_filters["language"])

        if "age_min" in segment_filters or "age_max" in segment_filters:
            today = timezone.now().date()

            if "age_max" in segment_filters:
                age_max = int(segment_filters["age_max"])
                min_dob = _subtract_years(today, age_max + 1) + datetime.timedelta(
                    days=1
                )
                user_qs = user_qs.filter(date_of_birth__gte=min_dob)

            if "age_min" in segment_filters:
                age_min = int(segment_filters["age_min"])
                max_dob = _subtract_years(today, age_min)
                user_qs = user_qs.filter(date_of_birth__lte=max_dob)

        user_ids: list[UUID] = list(user_qs.values_list("id", flat=True))
        notifications: list[Notification] = Notification.objects.bulk_create(
            [
                Notification(
                    recipient_id=uid,
                    sender=None,
                    notification_type=Notification.NotificationType.SYSTEM_BROADCAST,
                    title=title,
                    body=body,
                    data={"broadcast": True, "filters": segment_filters},
                )
                for uid in user_ids
            ]
        )
        AdminLogService.log_action(
            admin_user=admin_user,
            action=AdminLog.ActionType.BROADCAST,
            target_model="notifications.Notification",
            target_id="broadcast",
            detail=f"Broadcast sent to {len(notifications)} users: {title}.",
            metadata={
                "recipient_count": len(notifications),
                "filters": segment_filters,
            },
        )

        return notifications

    @staticmethod
    def list_broadcasts() -> QuerySet[Notification]:
        """Return unique broadcast notifications, newest first.
        Groups by title + created_at to avoid duplicate rows (one per recipient).
        """

        return (
            Notification.objects.filter(
                notification_type=Notification.NotificationType.SYSTEM_BROADCAST,
                data__broadcast=True,
            )
            .order_by("-created_at", "title")
            .distinct("created_at", "title")
        )

    @staticmethod
    def get_broadcast_detail(notification_id: UUID) -> dict[str, Any]:
        """Return a broadcast notification together with delivery stats.
        Because broadcasts produce one ``Notification`` row per recipient,
        we look up all notifications sharing the same title, body, and
        broadcast data.
        """
        notification: Notification = Notification.objects.get(
            pk=notification_id,
        )
        batch_qs: QuerySet[Notification] = Notification.objects.filter(
            notification_type=Notification.NotificationType.SYSTEM_BROADCAST,
            title=notification.title,
            body=notification.body,
            created_at=notification.created_at,
        )
        total_sent: int = batch_qs.count()
        total_read: int = batch_qs.filter(is_read=True).count()

        return {
            "notification": notification,
            "total_sent": total_sent,
            "total_read": total_read,
            "read_rate": (total_read / total_sent * 100) if total_sent else 0.0,
        }


class AdminAnalyticsService:
    """Platform-wide analytics and demographic reports."""

    @staticmethod
    def get_user_demographics() -> dict[str, Any]:
        """Return aggregated demographic data for the user base."""
        now = timezone.now()
        today = now.date()
        users = User.objects.filter(is_active=True)
        age_buckets: dict[str, int] = {
            "under_18": 0,
            "18_24": 0,
            "25_34": 0,
            "35_44": 0,
            "45_54": 0,
            "55_plus": 0,
        }

        for dob in users.values_list("date_of_birth", flat=True).iterator():
            if dob is None:
                continue

            age: int = (
                today.year
                - dob.year
                - ((today.month, today.day) < (dob.month, dob.day))
            )

            if age < 18:
                age_buckets["under_18"] += 1

            elif age <= 24:
                age_buckets["18_24"] += 1

            elif age <= 34:
                age_buckets["25_34"] += 1

            elif age <= 44:
                age_buckets["35_44"] += 1

            elif age <= 54:
                age_buckets["45_54"] += 1

            else:
                age_buckets["55_plus"] += 1

        gender_split = list(
            users.values("gender").annotate(count=Count("id")).order_by("gender")
        )
        country_top_10 = list(
            users.values("country").annotate(count=Count("id")).order_by("-count")[:10]
        )
        language_distribution = list(
            users.values("preferred_language")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return {
            "age_distribution": age_buckets,
            "gender_split": gender_split,
            "country_top_10": country_top_10,
            "language_distribution": language_distribution,
        }

    @staticmethod
    def get_content_engagement(days: int = 30) -> dict[str, Any]:
        """Return daily engagement metrics for the last *days* days."""
        since = timezone.now() - datetime.timedelta(days=days)
        posts_per_day = list(
            Post.objects.filter(created_at__gte=since)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )
        prayers_per_day = list(
            Prayer.objects.filter(created_at__gte=since)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )
        comments_per_day = list(
            Comment.objects.filter(created_at__gte=since)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )
        from apps.social.models import Reaction

        reactions_per_day = list(
            Reaction.objects.filter(created_at__gte=since)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        return {
            "posts_per_day": posts_per_day,
            "prayers_per_day": prayers_per_day,
            "comments_per_day": comments_per_day,
            "reactions_per_day": reactions_per_day,
        }

    @staticmethod
    def get_bible_reading_stats() -> dict[str, Any]:
        """Return PostView counts scoped to bible-related content types."""
        page_ct = ContentType.objects.get_for_model(SegregatedPage)
        chapter_ct = ContentType.objects.get_for_model(SegregatedChapter)
        total_page_views: int = PostView.objects.filter(
            content_type__in=[page_ct, chapter_ct],
        ).count()
        views_per_section = list(
            PostView.objects.filter(content_type=page_ct)
            .values(
                section_title=F("object_id"),
            )
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        return {
            "total_bible_views": total_page_views,
            "views_breakdown": views_per_section,
        }

    @staticmethod
    def get_shop_revenue(days: int = 30) -> dict[str, Any]:
        """Return daily purchase counts with product breakdown."""
        since = timezone.now() - datetime.timedelta(days=days)
        purchases_per_day = list(
            Purchase.objects.filter(created_at__gte=since)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )
        by_product = list(
            Purchase.objects.filter(created_at__gte=since)
            .values(product_title=F("product__title"))
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return {
            "purchases_per_day": purchases_per_day,
            "by_product": by_product,
        }

    @staticmethod
    def get_boost_performance() -> dict[str, Any]:
        """Return aggregate boost performance metrics."""
        total_boosts: int = PostBoost.objects.count()
        active_boosts: int = PostBoost.objects.filter(is_active=True).count()
        aggregate = BoostAnalyticSnapshot.objects.aggregate(
            total_impressions=Sum("impressions"),
            total_reach=Sum("reach"),
            avg_engagement_rate=Avg("engagement_rate"),
            total_link_clicks=Sum("link_clicks"),
            total_profile_visits=Sum("profile_visits"),
        )

        return {
            "total_boosts": total_boosts,
            "active_boosts": active_boosts,
            "total_impressions": aggregate["total_impressions"] or 0,
            "total_reach": aggregate["total_reach"] or 0,
            "avg_engagement_rate": float(
                aggregate["avg_engagement_rate"] or 0,
            ),
            "total_link_clicks": aggregate["total_link_clicks"] or 0,
            "total_profile_visits": aggregate["total_profile_visits"] or 0,
        }
