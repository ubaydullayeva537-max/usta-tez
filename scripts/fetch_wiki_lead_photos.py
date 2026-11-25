import httpx
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance

PROJECT_DIR = Path(r"C:\Users\KIUT\.gemini\antigravity\scratch\usta-xizmati")
DOWNLOAD_DIR = PROJECT_DIR / "scripts" / "downloaded_photos"
SERVICES_DIR = PROJECT_DIR / "app" / "static" / "images" / "services"

# Map services needing crisp on-topic photos -> Wikipedia article titles (in priority order)
WIKI_ARTICLES = {
    "tom-yopish": ["Metal roof", "Roofing", "Roofer"],
    "kafelchi": ["Tile", "Ceramic tile", "Porcelain tile"],
    "suvoq-boyoq": ["House painter and decorator", "Paint roller", "Plasterer"],
    "santexnik": ["Plumber", "Plumbing", "Tap (valve)"],
    "elektrik": ["Electrician", "Distribution board", "Circuit breaker"],
    "konditsioner": ["Air conditioning", "HVAC"],
    "wifi-ornatish": ["Wireless router", "Wi-Fi"],
    "issiq-pol": ["Underfloor heating", "Hydronics", "Radiant heating"],
    "video-kuzatuv": ["Closed-circuit television", "Security camera"],
    "kompyuter-ustasi": ["Computer repair technician", "Laptop"],
    "televizor-ustasi": ["Smart TV", "Television set", "LED-backlit LCD"],
    "soat-ustasi": ["Watchmaker", "Mechanical watch"],
    "maishiy-texnika": ["Washing machine", "Home appliance"],
    "mebelchi": ["Cabinetry", "Carpentry", "Kitchen cabinet"],
    "deraza-rom-eshik": ["Insulated glazing", "Casement window", "Door"],
    "yogoch-oymakorlik": ["Wood carving"],
    "mangal-quruvchi": ["Mangal (barbecue)", "Barbecue grill", "Tandoor"],
    "payvandlash": ["Welding", "Arc welding", "Welder"],
    "bogbon-landshaft": ["Landscaping", "Gardening", "Lawn"],
    "klining-dezinfeksiya": ["Cleaner", "Vacuum cleaner", "Carpet cleaning"],
}

ACCENT_COLORS = {
    "tom-yopish": (239, 68, 68),
    "kafelchi": (14, 165, 233),
    "suvoq-boyoq": (168, 85, 247),
    "santexnik": (14, 165, 233),
    "elektrik": (245, 158, 11),
    "konditsioner": (6, 182, 212),
    "wifi-ornatish": (59, 130, 246),
    "issiq-pol": (249, 115, 22),
    "video-kuzatuv": (30, 64, 175),
    "kompyuter-ustasi": (99, 102, 241),
    "televizor-ustasi": (139, 92, 246),
    "soat-ustasi": (217, 119, 6),
    "maishiy-texnika": (20, 184, 166),
    "mebelchi": (180, 83, 9),
    "deraza-rom-eshik": (37, 99, 235),
    "yogoch-oymakorlik": (217, 119, 6),
    "mangal-quruvchi": (220, 38, 38),
    "payvandlash": (249, 115, 22),
    "bogbon-landshaft": (22, 163, 74),
    "klining-dezinfeksiya": (14, 165, 233),
}


def save_as_card_png(src_path: Path, out_path: Path, accent_rgb: tuple[int, int, int]) -> None:
    with Image.open(src_path) as im:
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            bg = Image.new("RGB", im.size, (248, 250, 252))
            rgba = im.convert("RGBA")
            bg.paste(rgba, mask=rgba.split()[3])
            im = bg
        else:
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


def get_wiki_lead_image(client: httpx.Client, title: str) -> str | None:
    r = client.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "format": "json",
            "prop": "pageimages",
            "piprop": "thumbnail|original",
            "pithumbsize": "1000",
            "titles": title,
            "redirects": "1",
        },
        timeout=20,
    )
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    for p in pages.values():
        thumb = p.get("thumbnail", {})
        if thumb.get("source") and not thumb["source"].lower().endswith(".svg.png"):
            return thumb["source"]
        orig = p.get("original", {})
        if orig.get("source") and not orig["source"].lower().endswith(".svg"):
            return orig["source"]
    return None


def main() -> None:
    headers = {"User-Agent": "UstaBorServiceCatalog/1.0 (dev@ustabor.local)"}
    with httpx.Client(headers=headers, follow_redirects=True) as client:
        for slug, titles in WIKI_ARTICLES.items():
            url = None
            chosen_title = None
            for t in titles:
                url = get_wiki_lead_image(client, t)
                if url:
                    chosen_title = t
                    break
            if not url:
                print(f"[MISS] {slug}")
                continue
            try:
                resp = client.get(url, timeout=30)
                resp.raise_for_status()
                raw_path = DOWNLOAD_DIR / f"{slug}_wiki.jpg"
                raw_path.write_bytes(resp.content)
                save_as_card_png(raw_path, SERVICES_DIR / f"{slug}.png", ACCENT_COLORS[slug])
                print(f"[OK] {slug} ({chosen_title}) <- {url}")
            except Exception as exc:
                print(f"[ERR] {slug}: {exc}")


if __name__ == "__main__":
    main()
