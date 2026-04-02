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
        detail = response.data.get("detail", response.data) if isinstance(response.data, dict) else response.data
        if isinstance(detail, list):
            message = detail[0] if detail else "An error occurred."
        elif isinstance(detail, dict):
            message = next(iter(detail.values()), "An error occurred.")
            if isinstance(message, list):
                message = message[0] if message else "An error occurred."
        else:
            message = detail
        response.data = {"message": str(message), "data": None}
    else:
        # Unhandled exception -- return a safe generic 500 response
        # to prevent traceback / schema / credential leakage.
        logger.exception(
            "Unhandled exception in %s",
            context.get("view", "unknown view"),
        )
        response = Response(
            {"message": "An unexpected error occurred.", "data": None},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
