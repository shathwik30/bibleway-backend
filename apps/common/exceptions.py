from __future__ import annotations
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler


class NotFoundError(APIException):
    status_code = status.HTTP_404_NOT_FOUND

    default_detail = "The requested resource was not found."

    default_code = "not_found"


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT

    default_detail = "This action conflicts with the current state."

    default_code = "conflict"


class ForbiddenError(APIException):
    status_code = status.HTTP_403_FORBIDDEN

    default_detail = "You do not have permission to perform this action."

    default_code = "forbidden"


class BadRequestError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    default_detail = "The request was invalid."

    default_code = "bad_request"


def custom_exception_handler(exc, context):
    """Wrap DRF exceptions in a consistent {message, data} envelope.

    Also handles non-DRF exceptions (database errors, third-party errors, etc.)
    to prevent traceback leakage in production.
    """

    import logging

    logger = logging.getLogger("apps.common.exceptions")

    response = exception_handler(exc, context)

    if response is not None:
        raw = response.data
        detail = raw.get("detail", raw) if isinstance(raw, dict) else raw

        if isinstance(detail, list):
            message = detail[0] if detail else "An error occurred."

        elif isinstance(detail, dict):
            first_value = next(iter(detail.values()), "An error occurred.")
            message = (
                first_value[0]
                if isinstance(first_value, list) and first_value
                else first_value
            )

        else:
            message = detail

        errors = None

        if isinstance(raw, dict) and "detail" not in raw:
            errors = raw

        elif isinstance(raw, dict) and isinstance(raw.get("detail"), dict):
            errors = raw["detail"]

        response.data = {"message": str(message), "data": errors}

    else:
        logger.exception(
            "Unhandled exception in %s",
            context.get("view", "unknown view"),
        )
        response = Response(
            {"message": "An unexpected error occurred.", "data": None},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
