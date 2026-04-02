from __future__ import annotations
from typing import TypeVar
from django.db import models

ModelType = TypeVar("ModelType", bound=models.Model)
