APP_NAME = "Unity Bundle Explorer"
APP_SHORT_NAME = "UBE"
APP_VERSION = "2.4h"
APP_BUILD = "348"


def full_title(context: str | None = None) -> str:
    base = f"{APP_NAME} ({APP_SHORT_NAME}) - Version {APP_VERSION} (Build {APP_BUILD})"
    return f"{APP_NAME} ({APP_SHORT_NAME}) - {context} - Version {APP_VERSION} (Build {APP_BUILD})" if context else base
