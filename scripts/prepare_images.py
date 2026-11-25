import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance

BRAIN_DIR = Path(r"C:\Users\KIUT\.gemini\antigravity\brain\7fc7f266-c40d-4d8b-b773-fc8d7791aa1c")
PROJECT_DIR = Path(r"C:\Users\KIUT\.gemini\antigravity\scratch\usta-xizmati")
IMAGES_DIR = PROJECT_DIR / "app" / "static" / "images"
SERVICES_DIR = IMAGES_DIR / "services"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
SERVICES_DIR.mkdir(parents=True, exist_ok=True)

HERO_SRC = BRAIN_DIR / "usta_xizmati_hero_1795597747559.jpg"
AUTO_SRC = BRAIN_DIR / "auto_ev_truck_service_card_warm_1795597766150.jpg"
RENO_SRC = BRAIN_DIR / "home_renovation_service_card_1795597754784.jpg"
HOME_SRC = BRAIN_DIR / "home_service_card_1795597760325.jpg"
ELEC_SRC = BRAIN_DIR / "electronics_repair_service_card_v2_1795597778793.jpg"
WOOD_SRC = BRAIN_DIR / "artisan_wood_brick_services_card_1795597759723.jpg"

# Copy hero
shutil.copy2(HERO_SRC, IMAGES_DIR / "hero.jpg")

# Service -> (source_image, crop_box_normalized (left, top, right, bottom), accent_rgb)
SERVICE_VISUALS = {
    "avto-ustalari": (AUTO_SRC, (0.05, 0.10, 0.85, 0.90), (245, 158, 11)),
    "elektromobil": (AUTO_SRC, (0.00, 0.05, 0.72, 0.82), (16, 185, 129)),
    "yuk-mashinalar": (AUTO_SRC, (0.28, 0.02, 1.00, 0.82), (59, 130, 246)),
    "uy-quruvchi": (RENO_SRC, (0.00, 0.00, 0.95, 0.95), (245, 158, 11)),
    "evro-remont": (RENO_SRC, (0.05, 0.15, 0.85, 0.95), (99, 102, 241)),
    "tom-yopish": (RENO_SRC, (0.20, 0.00, 0.98, 0.72), (239, 68, 68)),
    "gisht-urish": (RENO_SRC, (0.25, 0.15, 1.00, 0.90), (234, 88, 12)),
    "kafelchi": (RENO_SRC, (0.00, 0.30, 0.82, 1.00), (14, 165, 233)),
    "suvoq-boyoq": (RENO_SRC, (0.12, 0.08, 0.88, 0.88), (168, 85, 247)),
    "santexnik": (HOME_SRC, (0.25, 0.25, 1.00, 0.95), (14, 165, 233)),
    "elektrik": (HOME_SRC, (0.18, 0.05, 0.92, 0.80), (245, 158, 11)),
    "konditsioner": (HOME_SRC, (0.00, 0.00, 0.78, 0.78), (6, 182, 212)),
    "wifi-ornatish": (ELEC_SRC, (0.25, 0.05, 0.98, 0.80), (59, 130, 246)),
    "issiq-pol": (HOME_SRC, (0.20, 0.30, 0.95, 1.00), (249, 115, 22)),
    "video-kuzatuv": (ELEC_SRC, (0.15, 0.00, 0.90, 0.75), (30, 64, 175)),
    "quyosh-panellari": (RENO_SRC, (0.15, 0.00, 0.95, 0.75), (234, 179, 8)),
    "kompyuter-ustasi": (ELEC_SRC, (0.00, 0.15, 0.75, 0.92), (99, 102, 241)),
    "telefon-ustasi": (ELEC_SRC, (0.10, 0.25, 0.82, 1.00), (16, 185, 129)),
    "televizor-ustasi": (ELEC_SRC, (0.22, 0.00, 1.00, 0.72), (139, 92, 246)),
    "soat-ustasi": (ELEC_SRC, (0.22, 0.28, 0.95, 1.00), (217, 119, 6)),
    "maishiy-texnika": (HOME_SRC, (0.18, 0.28, 0.98, 1.00), (20, 184, 166)),
    "gaz-plita": (HOME_SRC, (0.10, 0.20, 0.85, 0.95), (239, 68, 68)),
    "mebelchi": (WOOD_SRC, (0.00, 0.10, 0.80, 0.92), (180, 83, 9)),
    "deraza-rom-eshik": (WOOD_SRC, (0.15, 0.00, 0.95, 0.82), (37, 99, 235)),
    "yogoch-oymakorlik": (WOOD_SRC, (0.00, 0.22, 0.78, 1.00), (217, 119, 6)),
    "mangal-quruvchi": (WOOD_SRC, (0.25, 0.08, 1.00, 0.92), (220, 38, 38)),
    "payvandlash": (AUTO_SRC, (0.18, 0.15, 0.95, 0.95), (249, 115, 22)),
    "bogbon-landshaft": (WOOD_SRC, (0.20, 0.00, 0.98, 0.78), (22, 163, 74)),
    "qulf-ochish": (WOOD_SRC, (0.10, 0.12, 0.85, 0.88), (71, 85, 105)),
    "klining-dezinfeksiya": (HOME_SRC, (0.05, 0.15, 0.88, 0.95), (14, 165, 233)),
}


def make_card_image(src_path: Path, norm_box: tuple, accent_rgb: tuple, out_path: Path) -> None:
    with Image.open(src_path) as im:
        im = im.convert("RGB")
        w, h = im.size
        crop_box = (
            int(norm_box[0] * w),
            int(norm_box[1] * h),
            int(norm_box[2] * w),
            int(norm_box[3] * h),
        )
        cropped = im.crop(crop_box)
        # Maintain crisp 4:3 card aspect ratio (800x600)
        target_w, target_h = 800, 600
        src_ratio = cropped.width / cropped.height
        tgt_ratio = target_w / target_h
        if src_ratio > tgt_ratio:
            new_w = int(cropped.height * tgt_ratio)
            offset = (cropped.width - new_w) // 2
            cropped = cropped.crop((offset, 0, offset + new_w, cropped.height))
        else:
            new_h = int(cropped.width / tgt_ratio)
            offset = (cropped.height - new_h) // 2
            cropped = cropped.crop((0, offset, cropped.width, offset + new_h))

        resized = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
        resized = ImageEnhance.Contrast(resized).enhance(1.05)
        resized = ImageEnhance.Color(resized).enhance(1.04)

        # Subtle bottom accent bar (6px) for visual polish without obstructing photo
        draw = ImageDraw.Draw(resized)
        draw.rectangle([(0, target_h - 8), (target_w, target_h)], fill=accent_rgb)
        resized.save(out_path, format="PNG", optimize=True)


for slug, (src, box, color) in SERVICE_VISUALS.items():
    make_card_image(src, box, color, SERVICES_DIR / f"{slug}.png")

print(f"Generated hero.jpg and {len(SERVICE_VISUALS)} service images in {SERVICES_DIR}")
