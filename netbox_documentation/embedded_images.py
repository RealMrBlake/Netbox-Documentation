import base64
from io import BytesIO
import re
from django.utils.translation import gettext as _


class EmbeddedImageError(ValueError):
    pass


DATA_IMAGE_RE = re.compile(
    r"(?P<prefix>src\s*=\s*(?P<quote>['\"]))"
    r"data:(?P<mime>image/(?:png|jpeg|gif|webp));base64,(?P<data>[^'\"]+)"
    r"(?P=quote)",
    re.IGNORECASE,
)


def _decode(match):
    payload = re.sub(r"\s+", "", match.group("data"))
    try:
        content = base64.b64decode(payload, validate=True)
    except (ValueError, TypeError) as exc:
        raise EmbeddedImageError(_("A pasted image contains invalid Base64 data.")) from exc
    try:
        from PIL import Image
        image = Image.open(BytesIO(content))
        image.verify()
    except Exception as exc:
        raise EmbeddedImageError(_("Pasted content is not a valid image file.")) from exc
    return match.group("mime").lower(), content


def validate_embedded_images(html, max_total_bytes):
    total = 0
    for match in DATA_IMAGE_RE.finditer(html or ""):
        _mime, content = _decode(match)
        total += len(content)
        if total > max_total_bytes:
            raise EmbeddedImageError(_("The pasted images exceed the allowed total size."))


def store_embedded_images(html, max_total_bytes, store):
    total = 0

    def replace(match):
        nonlocal total
        mime, content = _decode(match)
        total += len(content)
        if total > max_total_bytes:
            raise EmbeddedImageError(_("The pasted images exceed the allowed total size."))
        url = store(mime, content)
        return f'{match.group("prefix")}{url}{match.group("quote")}'

    return DATA_IMAGE_RE.sub(replace, html or "")
