import base64
from io import BytesIO
import importlib.util
from pathlib import Path
import sys

from PIL import Image


spec = importlib.util.spec_from_file_location(
    "documentation_embedded_images",
    Path(__file__).parents[1] / "netbox_documentation" / "embedded_images.py",
)
embedded = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = embedded
spec.loader.exec_module(embedded)


def image_data_url():
    stream = BytesIO()
    Image.new("RGB", (2, 2), "red").save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode()


def test_embedded_image_is_replaced_with_stored_url():
    html = f'<p><img alt="Test" src="{image_data_url()}"></p>'
    stored = []

    def store(mime, content):
        stored.append((mime, content))
        return "/media/documentation/bild.png"

    result = embedded.store_embedded_images(html, 1024 * 1024, store)

    assert 'src="/media/documentation/bild.png"' in result
    assert "data:image/" not in result
    assert stored[0][0] == "image/png"
    assert stored[0][1]


def test_embedded_images_respect_total_size_limit():
    html = f'<img src="{image_data_url()}">'
    try:
        embedded.validate_embedded_images(html, 1)
    except embedded.EmbeddedImageError as exc:
        assert "total size" in str(exc)
    else:
        raise AssertionError("size limit was not applied")
