from urllib.parse import urlsplit


def require_remote_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Remote tool connections require an HTTP or HTTPS URL")
    return value
