import os
from decouple import config

_env = config("DJANGO_ENV", default="dev")

_module = os.environ.get("DJANGO_SETTINGS_MODULE", "")

if _module == "config.settings" or not _module:
    if _env == "prod":
        from .prod import *

    else:
        from .dev import *
