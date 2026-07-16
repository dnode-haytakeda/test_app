from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

_PACKAGE_NAME = "my-app-backend"
_FALLBACK = "0.0.0+unknown"

def get_version() -> str:
    try:
        return _pkg_version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return _FALLBACK


APP_VERSION = get_version()