"""
Seed Bible theme wallpapers into the shop as $1 products.

Usage:
    python manage.py seed_themes /path/to/themes/
    python manage.py seed_themes /path/to/themes/ --clear
"""

from __future__ import annotations
from pathlib import Path
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.shop.models import Product

CATEGORY = "wallpaper"

PRICE_TIER = "tier_1"

APPLE_PRODUCT_ID = "com.bibleway.wallpaper"

GOOGLE_PRODUCT_ID = "bibleway_wallpaper"


class Command(BaseCommand):
    help = "Seed Bible theme wallpapers from a directory of JPEG images."

    def add_arguments(self, parser):
        parser.add_argument(
            "source_dir",
            type=str,
            help="Path to directory containing theme JPEG files.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing wallpaper products first.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        source_dir = Path(options["source_dir"])

        if not source_dir.is_dir():
            raise CommandError(f"Directory not found: {source_dir}")

        if options["clear"]:
            deleted, _ = Product.objects.filter(category=CATEGORY).delete()
            self.stdout.write(
                self.style.WARNING(f"Cleared {deleted} existing wallpaper products.")
            )

        image_files = sorted(
            source_dir.glob("*.jpg"),
            key=lambda p: int(p.stem) if p.stem.isdigit() else 0,
        )

        if not image_files:
            raise CommandError(f"No .jpg files found in {source_dir}")

        created = 0

        for img_path in image_files:
            number = img_path.stem
            title = f"Bible Theme Wallpaper #{number}"
            product = Product(
                title=title,
                description=f"Beautiful Bible-themed wallpaper #{number}. Perfect for your phone or tablet background.",
                category=CATEGORY,
                is_free=False,
                price_tier=PRICE_TIER,
                apple_product_id=APPLE_PRODUCT_ID,
                google_product_id=GOOGLE_PRODUCT_ID,
                is_active=True,
            )
            product.save()
            image_bytes = img_path.read_bytes()
            product.cover_image.save(
                f"theme_{number}.jpg",
                ContentFile(image_bytes),
                save=True,
            )
            product.product_file.save(
                f"theme_{number}_full.jpg",
                ContentFile(image_bytes),
                save=True,
            )
            created += 1

            if created % 10 == 0:
                self.stdout.write(f"  {created} products created...")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Created {created} wallpaper products at ${PRICE_TIER}."
            )
        )
