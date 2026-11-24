"""Unit tests for the front/side/back collage."""

import io

import pytest
from PIL import Image

from app.collage import layout, make_collage

RED, GREEN, BLUE, WHITE = (255, 0, 0), (0, 200, 0), (0, 0, 255), (255, 255, 255)


def image(color, size=(400, 600), mode="RGB", fmt="PNG") -> bytes:
    out = io.BytesIO()
    Image.new(mode, size, color).save(out, fmt)
    return out.getvalue()


def open_jpeg(data: bytes) -> Image.Image:
    result = Image.open(io.BytesIO(data))
    assert result.format == "JPEG"
    return result.convert("RGB")


def close(actual, expected, tolerance=12) -> bool:
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected, strict=True))


def centre(box) -> tuple[int, int]:
    return box.left + box.width // 2, box.top + box.height // 2


@pytest.mark.parametrize(("size", "gap"), [(1200, 8), (900, 0), (1001, 7)])
def test_layout_fills_the_canvas_without_overlap(size, gap):
    boxes = layout(size, gap)
    front, side, back = boxes["front"], boxes["side"], boxes["back"]
    assert front.width > side.width and front.height > side.height
    assert side.left == back.left == front.left + front.width + gap
    assert back.top == side.top + side.height + gap
    assert side.left + side.width == size - gap
    assert back.top + back.height == size - gap
    assert front.top + front.height == size - gap


def test_default_panels_are_portrait_two_by_three():
    for box in layout(1200, 8).values():
        assert box.width / box.height == pytest.approx(2 / 3, abs=0.01)


def test_each_view_lands_in_its_panel():
    result = open_jpeg(make_collage(image(RED), image(GREEN), image(BLUE), size=1200))
    assert result.size == (1200, 1200)
    boxes = layout(1200, 8)
    assert close(result.getpixel(centre(boxes["front"])), RED)
    assert close(result.getpixel(centre(boxes["side"])), GREEN)
    assert close(result.getpixel(centre(boxes["back"])), BLUE)
    assert close(result.getpixel((2, 2)), WHITE)


def test_wide_image_is_letterboxed_not_cropped():
    wide = image(RED, size=(1200, 400))
    result = open_jpeg(make_collage(wide, image(GREEN), image(BLUE), size=1200, gap=0))
    front = layout(1200, 0)["front"]
    x, y = centre(front)
    assert close(result.getpixel((x, y)), RED)
    # Scaled to the panel's width, so the bands above and below stay background.
    assert close(result.getpixel((x, front.top + 5)), WHITE)
    assert close(result.getpixel((x, front.top + front.height - 5)), WHITE)
    # Not cropped: the full width is kept.
    assert close(result.getpixel((front.left + 3, y)), RED)


def test_transparent_png_is_flattened_onto_the_background():
    clear = image((0, 0, 0, 0), mode="RGBA")
    result = open_jpeg(make_collage(clear, image(GREEN), image(BLUE), background=(10, 20, 30)))
    assert close(result.getpixel(centre(layout(1200, 8)["front"])), (10, 20, 30))


def test_accepts_jpeg_and_webp_inputs():
    result = open_jpeg(
        make_collage(image(RED, fmt="JPEG"), image(GREEN, fmt="WEBP"), image(BLUE), size=600)
    )
    assert close(result.getpixel(centre(layout(600, 8)["side"])), GREEN)


def test_rejects_bytes_that_are_not_an_image():
    with pytest.raises(OSError):
        make_collage(b"not an image", image(GREEN), image(BLUE))
