from decouple import config

environment = config("DJANGO_ENV", default="dev")

if environment == "prod":
    from .prod import *  # noqa: F401, F403
else:
    from .dev import *  # noqa: F401, F403
