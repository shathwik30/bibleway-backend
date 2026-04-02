from __future__ import annotations
from django.urls import path
from .views import TodayVerseView, VerseByDateView

app_name = "verse_of_day"

urlpatterns = [
    path("today/", TodayVerseView.as_view(), name="today-verse"),
    path("<str:date_str>/", VerseByDateView.as_view(), name="verse-by-date"),
]
