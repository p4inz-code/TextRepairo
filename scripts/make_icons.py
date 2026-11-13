"""Render the app icon (PNG, ICO, ICNS) from code. Needs Pillow."""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "packaging"
GREEN = (31, 122, 99, 255)
WHITE = (255, 255, 255, 255)


def render(size: int = 1024) -> Image.Image:
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.28), fill=GREEN)
    w = int(s * 0.085)
    # letter T
    d.rounded_rectangle((s * 0.27, s * 0.28, s * 0.73, s * 0.28 + w), radius=w // 2, fill=WHITE)
    d.rounded_rectangle((s * 0.5 - w / 2, s * 0.28, s * 0.5 + w / 2, s * 0.74), radius=w // 2, fill=WHITE)
    # check mark
    pts = [(s * 0.60, s * 0.68), (s * 0.67, s * 0.75), (s * 0.80, s * 0.58)]
    cw = int(s * 0.06)
    d.line(pts, fill=(255, 255, 255, 215), width=cw, joint="curve")
    for p in (pts[0], pts[-1]):
        d.ellipse((p[0] - cw / 2, p[1] - cw / 2, p[0] + cw / 2, p[1] + cw / 2), fill=(255, 255, 255, 215))
    return img


def main() -> None:
    OUT.mkdir(exist_ok=True)
    big = render(1024)
    big.resize((512, 512), Image.LANCZOS).save(OUT / "icon.png")
    big.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    big.save(OUT / "icon.icns")
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
