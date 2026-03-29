"""
Seed the segregated Bible study content from markdown files.

Usage:
    python manage.py seed_segregated /path/to/ABC/
    python manage.py seed_segregated /path/to/ABC/ --clear  # wipe existing data first
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.bible.models import SegregatedChapter, SegregatedPage, SegregatedSection


FILE_TO_SECTION: list[dict[str, Any]] = [
    {
        "filename": "children sg bible.md",
        "title": "Children's Bible",
        "age_min": 4,
        "age_max": 12,
        "order": 0,
    },
    {
        "filename": "Introduction to the Teen Bible.md",
        "title": "Teen Bible",
        "age_min": 13,
        "age_max": 17,
        "order": 1,
    },
    {
        "filename": "Adult Stage\u20131 (Ages 18\u201326)_.md",
        "title": "Adult Stage-1: Autonomy & Choices",
        "age_min": 18,
        "age_max": 26,
        "order": 2,
    },
    {
        "filename": "Adult Bible Study \u2013 Stage 2 (Ages 27\u201331).md",
        "title": "Adult Stage-2: From Uncertainty to Calling",
        "age_min": 27,
        "age_max": 31,
        "order": 3,
    },
    {
        "filename": "Adult Stage-3 Bible Study (Age 32\u201340).md",
        "title": "Adult Stage-3: Making Commitments",
        "age_min": 32,
        "age_max": 40,
        "order": 4,
    },
    {
        "filename": "Adult Stage\u20134_ Mid-Life Transition (Ages 41\u201348).md",
        "title": "Adult Stage-4: Mid-Life Transition",
        "age_min": 41,
        "age_max": 48,
        "order": 5,
    },
    {
        "filename": "Adult Stage\u20135_ Leaving a Legacy (Ages 49\u201365).md",
        "title": "Adult Stage-5: Leaving a Legacy",
        "age_min": 49,
        "age_max": 65,
        "order": 6,
    },
    {
        "filename": "Senior Stage_ Spiritual Denouement (Ages 66 and Beyond).md",
        "title": "Senior Stage: Spiritual Denouement",
        "age_min": 66,
        "age_max": 120,
        "order": 7,
    },
]


def _clean_heading(text: str) -> str:
    text = re.sub(r"[*_#]+", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:255]


def _split_into_chapters(content: str) -> list[dict[str, str]]:
    pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(content))

    if not matches:
        return [{"title": "Introduction", "content": content.strip()}]

    chapters: list[dict[str, str]] = []

    if matches[0].start() > 0:
        intro = content[: matches[0].start()].strip()
        if intro:
            chapters.append({"title": "Introduction", "content": intro})

    for i, match in enumerate(matches):
        title = _clean_heading(match.group(2))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        if title and body:
            chapters.append({"title": title, "content": body})

    return chapters


class Command(BaseCommand):
    help = "Seed segregated Bible sections, chapters, and pages from markdown files."

    def add_arguments(self, parser):
        parser.add_argument("source_dir", type=str, help="Path to the directory containing markdown files.")
        parser.add_argument("--clear", action="store_true", help="Delete all existing segregated data before seeding.")

    @transaction.atomic
    def handle(self, *args, **options):
        source_dir = Path(options["source_dir"])
        if not source_dir.is_dir():
            raise CommandError(f"Directory not found: {source_dir}")

        if options["clear"]:
            deleted_sections, _ = SegregatedSection.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted_sections} existing sections (cascade)."))

        total_chapters = 0
        total_pages = 0

        for mapping in FILE_TO_SECTION:
            filepath = source_dir / mapping["filename"]
            if not filepath.exists():
                self.stdout.write(self.style.WARNING(f"Skipping missing file: {mapping['filename']}"))
                continue

            content = filepath.read_text(encoding="utf-8")

            section = SegregatedSection.objects.create(
                title=mapping["title"],
                age_min=mapping["age_min"],
                age_max=mapping["age_max"],
                order=mapping["order"],
                is_active=True,
            )

            chapters_data = _split_into_chapters(content)

            for ch_order, ch_data in enumerate(chapters_data):
                chapter = SegregatedChapter.objects.create(
                    section=section,
                    title=ch_data["title"],
                    order=ch_order,
                    is_active=True,
                )

                SegregatedPage.objects.create(
                    chapter=chapter,
                    title=ch_data["title"],
                    content=ch_data["content"],
                    order=0,
                    is_active=True,
                )

                total_chapters += 1
                total_pages += 1

            self.stdout.write(
                f"  {section.title} (ages {section.age_min}-{section.age_max}): "
                f"{len(chapters_data)} chapters"
            )

        self.stdout.write(self.style.SUCCESS(
            f"\nDone! Created {len(FILE_TO_SECTION)} sections, "
            f"{total_chapters} chapters, {total_pages} pages."
        ))
