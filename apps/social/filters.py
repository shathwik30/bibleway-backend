from __future__ import annotations
import django_filters
from .models import Post, Prayer


class PostFilter(django_filters.FilterSet):
    class Meta:
        model = Post
        fields = {
            "author": ["exact"],
            "is_boosted": ["exact"],
            "created_at": ["gte", "lte"],
        }


class PrayerFilter(django_filters.FilterSet):
    class Meta:
        model = Prayer
        fields = {
            "author": ["exact"],
            "created_at": ["gte", "lte"],
        }
