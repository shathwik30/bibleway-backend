from __future__ import annotations

from typing import Any, Generic, Sequence
from uuid import UUID

from django.db import models
from django.db.models import QuerySet

from .exceptions import NotFoundError
from .types import ModelType


class BaseService(Generic[ModelType]):
    """Generic service base class providing standard CRUD operations.

    Subclass and set `model` to the Django model class.
    Override methods to add business logic.

    Usage:
        class PostService(BaseService[Post]):
            model = Post

            def get_queryset(self) -> QuerySet[Post]:
                return super().get_queryset().select_related("author")
    """

    model: type[ModelType]

    def get_queryset(self) -> QuerySet[ModelType]:
        """Return the base queryset. Override to add select_related, prefetch, etc."""
        return self.model.objects.all()

    def get_by_id(self, pk: UUID) -> ModelType:
        """Retrieve a single instance by primary key. Raises NotFoundError if not found."""
        try:
            return self.get_queryset().get(pk=pk)
        except self.model.DoesNotExist:
            raise NotFoundError(
                detail=f"{self.model.__name__} with id '{pk}' not found."
            )

    def get_by_id_or_none(self, pk: UUID) -> ModelType | None:
        """Retrieve a single instance by primary key, or None."""
        try:
            return self.get_queryset().get(pk=pk)
        except self.model.DoesNotExist:
            return None

    def get_list(self, **filters: Any) -> QuerySet[ModelType]:
        """Return a filtered queryset."""
        return self.get_queryset().filter(**filters)

    def create(self, **kwargs: Any) -> ModelType:
        """Create and return a new instance with model validation."""
        instance = self.model(**kwargs)
        instance.full_clean()
        instance.save()
        return instance

    # Subclasses should set this to restrict which fields can be updated
    # via the generic update() method.  When empty, all model fields are
    # allowed (preserve backward compatibility).
    allowed_update_fields: set[str] = set()

    def update(self, instance: ModelType, **kwargs: Any) -> ModelType:
        """Update an instance with the given keyword arguments.

        If ``allowed_update_fields`` is defined on the service subclass,
        only those fields may be updated.  Any unrecognised field names
        are silently ignored rather than being set via ``setattr``,
        preventing mass-assignment of sensitive attributes.
        """
        allowed = self.allowed_update_fields
        model_field_names = {f.name for f in instance._meta.get_fields()}
        for field, value in kwargs.items():
            if allowed and field not in allowed:
                continue
            if field not in model_field_names:
                continue
            setattr(instance, field, value)
        instance.full_clean()
        update_fields: list[str] = [
            k for k in kwargs
            if k in model_field_names and (not allowed or k in allowed)
        ]
        if hasattr(instance, "updated_at"):
            update_fields.append("updated_at")
        instance.save(update_fields=update_fields)
        return instance

    def delete(self, instance: ModelType) -> None:
        """Delete an instance."""
        instance.delete()

    def exists(self, **filters: Any) -> bool:
        """Check if any instances matching the filters exist."""
        return self.get_queryset().filter(**filters).exists()

    def count(self, **filters: Any) -> int:
        """Count instances matching the filters."""
        return self.get_queryset().filter(**filters).count()

    def bulk_create(self, instances: Sequence[ModelType]) -> list[ModelType]:
        """Bulk create instances."""
        return self.model.objects.bulk_create(instances)


class BaseUserScopedService(BaseService[ModelType]):
    """Service that scopes queries to a specific user.

    Usage:
        class BookmarkService(BaseUserScopedService[Bookmark]):
            model = Bookmark
            user_field = "user"
    """

    user_field: str = "user"

    def get_user_queryset(self, user_id: UUID) -> QuerySet[ModelType]:
        """Return queryset filtered by user."""
        return self.get_queryset().filter(**{self.user_field: user_id})

    def list_for_user(self, user_id: UUID, **filters: Any) -> QuerySet[ModelType]:
        """Return filtered queryset for a specific user."""
        return self.get_user_queryset(user_id).filter(**filters)

    def get_for_user(self, user_id: UUID, pk: UUID) -> ModelType:
        """Retrieve a single instance owned by the user."""
        try:
            return self.get_user_queryset(user_id).get(pk=pk)
        except self.model.DoesNotExist:
            raise NotFoundError(
                detail=f"{self.model.__name__} with id '{pk}' not found."
            )
