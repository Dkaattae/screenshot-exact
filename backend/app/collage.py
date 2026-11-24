"""The try-on collage: front view large on the left, side and back stacked on the right.

Built from the three saved stills with Pillow, no AI. The stills are the source of truth;
the collage is derived from them and can be rebuilt at any time.

    ┌──────────────┬──────┐
    │              │ side │
    │    front     ├──────┤
    │              │ back │
    └──────────────┴──────┘

With the default square canvas every panel is 2:3 portrait, the usual shape of a full-body
photo. Each still is scaled to fit its panel without cropping, so no part of the outfit
is cut off, and centred on the background colour.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageOps


@dataclass(frozen=True)
class Box:
    left: int
    top: int
    width: int
    height: int


def layout(size: int, gap: int) -> dict[str, Box]:
    """Panel boxes for a square canvas of `size` pixels with `gap` pixels between panels."""
    inner = size - 2 * gap
    front_width = (inner - gap) * 2 // 3
    side_width = inner - gap - front_width
    side_height = (inner - gap) // 2
    right = gap + front_width + gap
    return {
        "front": Box(gap, gap, front_width, inner),
        "side": Box(right, gap, side_width, side_height),
        "back": Box(right, gap + side_height + gap, side_width, inner - gap - side_height),
    }


def make_collage(
    front: bytes,
    side: bytes,
    back: bytes,
    size: int = 1200,
    gap: int = 8,
    background: tuple[int, int, int] = (255, 255, 255),
    quality: int = 90,
) -> bytes:
    """Combine the three stills into one JPEG collage."""
    canvas = Image.new("RGB", (size, size), background)
    for view, data in (("front", front), ("side", side), ("back", back)):
        box = layout(size, gap)[view]
        image = _open(data, background)
        image = ImageOps.contain(image, (box.width, box.height), Image.Resampling.LANCZOS)
        canvas.paste(
            image,
            (
                box.left + (box.width - image.width) // 2,
                box.top + (box.height - image.height) // 2,
            ),
        )
    out = io.BytesIO()
    canvas.save(out, "JPEG", quality=quality, optimize=True)
    return out.getvalue()


def _open(data: bytes, background: tuple[int, int, int]) -> Image.Image:
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        flat = Image.new("RGB", image.size, background)
        flat.paste(image, mask=image.getchannel("A"))
        return flat
    return image.convert("RGB")
