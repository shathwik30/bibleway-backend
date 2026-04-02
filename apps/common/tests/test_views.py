from __future__ import annotations
import pytest
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from apps.common.pagination import StandardPageNumberPagination
from apps.common.views import BaseAPIView
from conftest import UserFactory


class _ContextEchoSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    request_path = serializers.SerializerMethodField()
    context_user_id = serializers.SerializerMethodField()

    def get_request_path(self, obj) -> str:
        return self.context["request"].path

    def get_context_user_id(self, obj) -> str:
        return str(self.context["user"].id)


class _TestAPIView(BaseAPIView):
    pagination_class = StandardPageNumberPagination


@pytest.mark.django_db
class TestBaseAPIView:
    def test_paginated_response_passes_request_and_user_context(self):
        user = UserFactory()
        factory = APIRequestFactory()
        drf_request = Request(factory.get("/api/v1/test/"))
        drf_request.user = user
        view = _TestAPIView()
        response = view.paginated_response([user], _ContextEchoSerializer, drf_request)
        result = response.data["data"]["results"][0]
        assert result["request_path"] == "/api/v1/test/"
        assert result["context_user_id"] == str(user.id)
