from django.conf import settings

PROTOCOL = "http" if settings.IS_DEV else "https"
PORT = ":8000" if settings.IS_DEV else ""

def local_url_to_email(local_url, display=""):
    if display:
        return f"[{display}]({PROTOCOL}://{settings.HOST_NAME}{PORT}{local_url})"
    else:
        return f"{PROTOCOL}://{settings.HOST_NAME}{PORT}{local_url}"
