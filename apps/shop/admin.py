from django.contrib import admin
from .models import Download, Product, Purchase


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "category",
        "is_free",
        "price_tier",
        "is_active",
        "download_count",
        "created_at",
    ]

    list_filter = ["is_free", "is_active", "category"]

    search_fields = ["title", "description"]

    readonly_fields = ["id", "download_count", "created_at", "updated_at"]


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "product",
        "platform",
        "transaction_id",
        "is_validated",
        "created_at",
    ]

    list_filter = ["platform", "is_validated"]

    search_fields = ["user__email", "product__title", "transaction_id"]

    readonly_fields = ["id", "created_at"]


@admin.register(Download)
class DownloadAdmin(admin.ModelAdmin):
    list_display = ["user", "product", "purchase", "created_at"]

    search_fields = ["user__email", "product__title"]

    readonly_fields = ["id", "created_at"]
