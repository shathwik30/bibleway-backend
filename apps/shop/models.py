from django.conf import settings
from django.db import models
from apps.common.models import CreatedAtModel, TimeStampedModel
from apps.common.storage_backends import PrivateMediaStorage, PublicMediaStorage


def product_cover_upload_path(instance: "Product", filename: str) -> str:
    return f"shop/{instance.id}/cover/{filename}"


def product_file_upload_path(instance: "Product", filename: str) -> str:
    return f"shop/{instance.id}/files/{filename}"


class Product(TimeStampedModel):
    """Digital product in the BibleWay shop."""

    title = models.CharField(max_length=255)
    description = models.TextField()
    cover_image = models.ImageField(
        upload_to=product_cover_upload_path,
        storage=PublicMediaStorage(),
    )

    product_file = models.FileField(
        upload_to=product_file_upload_path,
        storage=PrivateMediaStorage(),
        help_text="The downloadable file (PDF, ZIP, MP3, etc.). Served via pre-signed URLs.",
    )

    price_tier = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Maps to the IAP product ID for paid products.",
    )

    is_free = models.BooleanField(default=False, db_index=True)
    category = models.CharField(max_length=100, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    download_count = models.PositiveIntegerField(default=0)
    apple_product_id = models.CharField(max_length=100, blank=True, default="")
    google_product_id = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        verbose_name = "product"
        verbose_name_plural = "products"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["is_free", "is_active"]),
        ]

    def __str__(self) -> str:
        price_label = "Free" if self.is_free else self.price_tier

        return f"{self.title} ({price_label})"


class Purchase(CreatedAtModel):
    """Record of a user's purchase of a product.

    Receipt data is validated server-side against Apple/Google.
    """

    class Platform(models.TextChoices):
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="purchases",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="purchases",
    )

    platform = models.CharField(max_length=10, choices=Platform.choices)
    receipt_data = models.TextField(
        help_text="Raw receipt data from Apple/Google for server-side validation.",
    )

    transaction_id = models.CharField(max_length=255, unique=True, db_index=True)
    is_validated = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = "purchase"
        verbose_name_plural = "purchases"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["product"]),
            models.Index(fields=["user", "product"]),
        ]

    def __str__(self) -> str:
        return (
            f"Purchase by {self.user.full_name}: {self.product.title} ({self.platform})"
        )


class Download(CreatedAtModel):
    """Record of a file download. Tracks both free and paid downloads."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="downloads",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="downloads",
    )

    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="downloads",
        help_text="Null for free product downloads.",
    )

    class Meta:
        verbose_name = "download"
        verbose_name_plural = "downloads"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["product"]),
            models.Index(fields=["user", "product"]),
        ]

    def __str__(self) -> str:
        return f"Download by {self.user.full_name}: {self.product.title}"
