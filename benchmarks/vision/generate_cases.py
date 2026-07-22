from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


CASES = {
    "normal_001": [],
    "overflow_001": ["overflow"],
    "crowded_001": ["crowded"],
    "weak_hierarchy_001": ["weak_hierarchy"],
    "misalignment_001": ["misalignment"],
}


def _base() -> tuple[Image.Image, ImageDraw.ImageDraw, ImageFont.ImageFont]:
    image = Image.new("RGB", (1280, 720), "white")
    return image, ImageDraw.Draw(image), ImageFont.load_default(size=24)


def create_cases(output: Path) -> dict[str, str]:
    output.mkdir(parents=True, exist_ok=True)

    normal, draw, font = _base()
    draw.text((80, 60), "Project Summary", font=font, fill="#1F1F1F")
    draw.rectangle((80, 160, 560, 560), outline="#1F4E79", width=4)
    draw.text((120, 220), "Clear hierarchy", font=font, fill="#1F1F1F")
    normal.save(output / "normal_001.png")

    overflow = normal.copy()
    overflow_draw = ImageDraw.Draw(overflow)
    overflow_draw.rectangle((1120, 610, 1279, 719), fill="#FDE9E7", outline="#C00000", width=4)
    overflow_draw.text((1190, 670), "OVERFLOW_TEXT_OUTSIDE_SAFE_MARGIN", font=font, fill="#C00000")
    overflow.save(output / "overflow_001.png")

    crowded, crowded_draw, crowded_font = _base()
    for index in range(27):
        crowded_draw.text((30, 10 + index * 25), f"Dense line {index:02d}: repeated content without hierarchy", font=crowded_font, fill="#222222")
    crowded.save(output / "crowded_001.png")

    weak, weak_draw, weak_font = _base()
    for index, text in enumerate(("Quarterly Review", "Revenue increased", "Key risks", "Next actions")):
        weak_draw.text((90, 90 + index * 130), text, font=weak_font, fill="#333333")
    weak.save(output / "weak_hierarchy_001.png")

    misaligned, misaligned_draw, misaligned_font = _base()
    for index, x in enumerate((80, 355, 690, 930)):
        top = 150 + (index % 2) * 55
        misaligned_draw.rectangle((x, top, x + 220, top + 280), outline="#4472C4", width=4)
        misaligned_draw.text((x + 20, top + 30), f"Block {index + 1}", font=misaligned_font, fill="#222222")
    misaligned.save(output / "misalignment_001.png")

    return {
        name: sha256((output / f"{name}.png").read_bytes()).hexdigest()
        for name in CASES
    }


if __name__ == "__main__":
    target = Path("artifacts/m0/vision")
    for case_id, digest in create_cases(target).items():
        print(f"{case_id} {digest}")
