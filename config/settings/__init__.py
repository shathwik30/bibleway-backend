import os

from decouple import config

_env = config("DJANGO_ENV", default="dev")
_module = os.environ.get("DJANGO_SETTINGS_MODULE", "")

# Only auto-import when Django is using this package as the settings
# module (i.e. DJANGO_SETTINGS_MODULE == "config.settings").
# When a specific submodule is set (e.g. "config.settings.test"),
# Django loads that directly and this __init__ should be a no-op.
if _module == "config.settings" or not _module:
    if _env == "prod":
        from .prod import *  # noqa: F401, F403
    else:
        from .dev import *  # noqa: F401, F403
