import json
import time
from pathlib import Path
import httpx
from PIL import Image, ImageDraw, ImageEnhance

BRAIN_DIR = Path(r"C:\Users\KIUT\.gemini\antigravity\brain\7fc7f266-c40d-4d8b-b773-fc8d7791aa1c")
PROJECT_DIR = Path(r"C:\Users\KIUT\.gemini\antigravity\scratch\usta-xizmati")
DOWNLOAD_DIR = PROJECT_DIR / "scripts" / "downloaded_photos"
SERVICES_DIR = PROJECT_DIR / "app" / "static" / "images" / "services"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
SERVICES_DIR.mkdir(parents=True, exist_ok=True)

# Already generated photorealistic images
GENERATED = {
    "avto-ustalari": BRAIN_DIR / "avto_ustalari_1795599610762.jpg",
    "elektromobil": BRAIN_DIR / "elektromobil_service_card_1795599612077.jpg",
    "yuk-mashinalar": BRAIN_DIR / "yuk_mashinalar_1795599615725.jpg",
    "uy-quruvchi": BRAIN_DIR / "uy_quruvchi_service_card_1795599614851.jpg",
    "evro-remont": BRAIN_DIR / "evro_remont_service_card_1795599617932.jpg",
}

# Check if gisht-urish also finished
for p in BRAIN_DIR.glob("*gisht*"):
    if p.suffix.lower() in {".jpg", ".png", ".jpeg"}:
        GENERATED["gisht-urish"] = p
        break

# Curated Wikimedia Commons search queries per remaining service
WIKI_QUERIES = {
    "tom-yopish": ["metal roof installation roofer", "roofer installing roof tiles"],
    "gisht-urish": ["bricklayer laying bricks mortar", "masonry bricklaying wall"],
    "kafelchi": ["ceramic tile installation floor", "tiler laying ceramic tiles"],
    "suvoq-boyoq": ["interior wall painting roller", "house painter painting wall"],
    "santexnik": ["plumber fixing sink pipe wrench", "plumbing pipe installation"],
    "elektrik": ["electrician electrical panel multimeter", "electrician wiring circuit breaker"],
    "konditsioner": ["air conditioner split unit wall installation", "hvac air conditioner technician"],
    "wifi-ornatish": ["wireless wifi router ethernet cable", "wifi router home network"],
    "issiq-pol": ["underfloor heating pipes installation", "radiant floor heating tubing"],
    "video-kuzatuv": ["cctv security camera wall mounted", "surveillance dome camera building"],
    "quyosh-panellari": ["solar panel installation roof", "photovoltaic solar panels house roof"],
    "kompyuter-ustasi": ["laptop computer repair technician", "motherboard laptop repair workbench"],
    "telefon-ustasi": ["smartphone repair technician screen", "mobile phone repair tools"],
    "televizor-ustasi": ["television electronics repair workbench", "led tv repair technician"],
    "soat-ustasi": ["watchmaker repairing wristwatch movement", "watch repair loupe tweezers"],
    "maishiy-texnika": ["washing machine repair technician", "home appliance repair washing machine"],
    "gaz-plita": ["gas stove burner kitchen flame", "kitchen gas range burners"],
    "mebelchi": ["carpenter assembling wooden furniture cabinet", "woodworker kitchen cabinet installation"],
    "deraza-rom-eshik": ["window frame installation carpenter", "upvc window installation"],
    "yogoch-oymakorlik": ["wood carving chisel artisan", "traditional wood carving uzbekistan"],
    "mangal-quruvchi": ["brick barbecue grill outdoor masonry", "mangal brick grill charcoal"],
    "payvandlash": ["welder welding steel sparks workshop", "arc welding metal workshop"],
    "bogbon-landshaft": ["gardener trimming hedge lawn garden", "landscaping garden lawn care"],
    "qulf-ochish": ["locksmith door lock key installation", "door lock cylinder key"],
    "klining-dezinfeksiya": ["sofa upholstery cleaning vacuum cleaner", "professional carpet sofa cleaning"],
}

ACCENT_COLORS = {
    "avto-ustalari": (245, 158, 11),
    "elektromobil": (16, 185, 129),
    "yuk-mashinalar": (59, 130, 246),
    "uy-quruvchi": (245, 158, 11),
    "evro-remont": (99, 102, 241),
    "tom-yopish": (239, 68, 68),
    "gisht-urish": (234, 88, 12),
    "kafelchi": (14, 165, 233),
    "suvoq-boyoq": (168, 85, 247),
    "santexnik": (14, 165, 233),
    "elektrik": (245, 158, 11),
    "konditsioner": (6, 182, 212),
    "wifi-ornatish": (59, 130, 246),
    "issiq-pol": (249, 115, 22),
    "video-kuzatuv": (30, 64, 175),
    "quyosh-panellari": (234, 179, 8),
    "kompyuter-ustasi": (99, 102, 241),
    "telefon-ustasi": (16, 185, 129),
    "televizor-ustasi": (139, 92, 246),
    "soat-ustasi": (217, 119, 6),
    "maishiy-texnika": (20, 184, 166),
    "gaz-plita": (239, 68, 68),
    "mebelchi": (180, 83, 9),
    "deraza-rom-eshik": (37, 99, 235),
    "yogoch-oymakorlik": (217, 119, 6),
    "mangal-quruvchi": (220, 38, 38),
    "payvandlash": (249, 115, 22),
    "bogbon-landshaft": (22, 163, 74),
    "qulf-ochish": (71, 85, 105),
    "klining-dezinfeksiya": (14, 165, 233),
}


def search_wikimedia_image(client: httpx.Client, query: str) -> str | None:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",  # File namespace
        "gsrsearch": f"{query} filetype:bitmap",
        "gsrlimit": "10",
        "prop": "imageinfo",
        "iiprop": "url|size|mime",
        "iiurlwidth": "1000",
    }
    resp = client.get("https://commons.wikimedia.org/w/api.php", params=params, timeout=20)
    resp.raise_for_status()
    pages = resp.json().get("query", {}).get("pages", {})
    # Sort by page index so most relevant comes first
    sorted_pages = sorted(pages.values(), key=lambda p: p.get("index", 999))
    for page in sorted_pages:
        infos = page.get("imageinfo", [])
        if not infos:
            continue
        info = infos[0]
        mime = info.get("mime", "")
        w = info.get("width", 0)
        h = info.get("height", 0)
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        if w < 500 or h < 350:
            continue
        # Prefer landscape or near-square photos for 4:3 cards
        ratio = w / max(1, h)
        if ratio < 0.7 or ratio > 2.4:
            continue
        return info.get("thumburl") or info.get("url")
    return None


def save_as_card_png(src_path: Path, out_path: Path, accent_rgb: tuple[int, int, int]) -> None:
    with Image.open(src_path) as im:
        im = im.convert("RGB")
        target_w, target_h = 800, 600
        src_ratio = im.width / im.height
        tgt_ratio = target_w / target_h
        if src_ratio > tgt_ratio:
            new_w = int(im.height * tgt_ratio)
            offset = (im.width - new_w) // 2
            im = im.crop((offset, 0, offset + new_w, im.height))
        else:
            new_h = int(im.width / tgt_ratio)
            offset = (im.height - new_h) // 2
            im = im.crop((0, offset, im.width, offset + new_h))

        resized = im.resize((target_w, target_h), Image.Resampling.LANCZOS)
        resized = ImageEnhance.Contrast(resized).enhance(1.04)
        draw = ImageDraw.Draw(resized)
        draw.rectangle([(0, target_h - 6), (target_w, target_h)], fill=accent_rgb)
        resized.save(out_path, format="PNG", optimize=True)


def main() -> None:
    headers = {"User-Agent": "UstaBorServiceCatalog/1.0 (https://localhost; dev@ustabor.local)"}
    manifest = {}

    # 1. Process generated images first
    for slug, src_path in GENERATED.items():
        if src_path.exists():
            save_as_card_png(src_path, SERVICES_DIR / f"{slug}.png", ACCENT_COLORS[slug])
            manifest[slug] = f"generated:{src_path.name}"
            print(f"[GEN] {slug} -> {src_path.name}")

    # 2. Fetch remaining from Wikimedia Commons
    with httpx.Client(headers=headers, follow_redirects=True) as client:
        for slug, queries in WIKI_QUERIES.items():
            if slug in manifest:
                continue
            dest_raw = DOWNLOAD_DIR / f"{slug}.jpg"
            img_url = None
            for q in queries:
                try:
                    img_url = search_wikimedia_image(client, q)
                    if img_url:
                        break
                except Exception as exc:
                    print(f"[WARN] search failed for {slug} ({q}): {exc}")
                time.sleep(0.2)

            if not img_url:
                print(f"[MISS] No Wikimedia photo found for {slug}")
                continue

            try:
                r = client.get(img_url, timeout=30)
                r.raise_for_status()
                dest_raw.write_bytes(r.content)
                save_as_card_png(dest_raw, SERVICES_DIR / f"{slug}.png", ACCENT_COLORS[slug])
                manifest[slug] = img_url
                print(f"[OK] {slug} <- {img_url}")
            except Exception as exc:
                print(f"[ERR] download failed for {slug}: {exc}")
            time.sleep(0.2)

    (PROJECT_DIR / "scripts" / "image_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Done! Prepared {len(manifest)}/30 service images.")


if __name__ == "__main__":
    main()
