import httpx
from pathlib import Path
from PIL import Image, ImageDraw
from fetch_wiki_lead_photos import save_as_card_png, get_wiki_lead_image, ACCENT_COLORS, DOWNLOAD_DIR, SERVICES_DIR

BRAIN_DIR = Path(r"C:\Users\KIUT\.gemini\antigravity\brain\7fc7f266-c40d-4d8b-b773-fc8d7791aa1c")
HOME_SRC = BRAIN_DIR / "home_service_card_1795597760325.jpg"
RENO_SRC = BRAIN_DIR / "home_renovation_service_card_1795597754784.jpg"
WOOD_SRC = BRAIN_DIR / "artisan_wood_brick_services_card_1795597759723.jpg"

# 1. Restore Courtyard_creation_Kuching for bogbon-landshaft (already downloaded as bogbon-landshaft_wiki.jpg)
bogbon_wiki = DOWNLOAD_DIR / "bogbon-landshaft_wiki.jpg"
if bogbon_wiki.exists():
    save_as_card_png(bogbon_wiki, SERVICES_DIR / "bogbon-landshaft.png", ACCENT_COLORS["bogbon-landshaft"])
    print("[OK] bogbon-landshaft -> Courtyard landscaping photo")

# 2. Fetch crisp photos for klining-dezinfeksiya & deraza-rom-eshik from Wikipedia lead images
headers = {"User-Agent": "UstaBorServiceCatalog/1.0 (dev@ustabor.local)"}
with httpx.Client(headers=headers, follow_redirects=True) as client:
    for slug, titles in {
        "klining-dezinfeksiya": ["Window cleaner", "Pressure washing", "Steam cleaning"],
        "deraza-rom-eshik": ["Casement window", "French window", "Patio door"],
    }.items():
        for t in titles:
            url = get_wiki_lead_image(client, t)
            if url:
                r = client.get(url, timeout=30)
                r.raise_for_status()
                raw = DOWNLOAD_DIR / f"{slug}_v3.jpg"
                raw.write_bytes(r.content)
                save_as_card_png(raw, SERVICES_DIR / f"{slug}.png", ACCENT_COLORS[slug])
                print(f"[OK] {slug} ({t}) <- {url}")
                break

# 3. For konditsioner, elektrik, kafelchi: use focused high-res crops from our bespoke photorealistic generated cards
def crop_and_save(src: Path, box: tuple, slug: str):
    with Image.open(src) as im:
        w, h = im.size
        cropped = im.crop((int(box[0]*w), int(box[1]*h), int(box[2]*w), int(box[3]*h)))
        tmp = DOWNLOAD_DIR / f"{slug}_crop.jpg"
        cropped.save(tmp, format="JPEG", quality=95)
    save_as_card_png(tmp, SERVICES_DIR / f"{slug}.png", ACCENT_COLORS[slug])
    print(f"[CROP] {slug} <- {src.name}")

crop_and_save(HOME_SRC, (0.00, 0.00, 0.72, 0.72), "konditsioner")
crop_and_save(HOME_SRC, (0.30, 0.04, 0.96, 0.62), "elektrik")
crop_and_save(RENO_SRC, (0.00, 0.35, 0.75, 1.00), "kafelchi")

# Preview the 6 updated cards
sheet = Image.new("RGB", (3 * 400, 2 * 300), (15, 23, 42))
draw = ImageDraw.Draw(sheet)
targets = ["bogbon-landshaft", "deraza-rom-eshik", "elektrik", "kafelchi", "konditsioner", "klining-dezinfeksiya"]
for idx, slug in enumerate(targets):
    r, c = divmod(idx, 3)
    with Image.open(SERVICES_DIR / f"{slug}.png") as im:
        sheet.paste(im.resize((400, 300), Image.Resampling.LANCZOS), (c * 400, r * 300))
    draw.rectangle([(c * 400, r * 300), (c * 400 + 210, r * 300 + 26)], fill=(15, 23, 42))
    draw.text((c * 400 + 8, r * 300 + 6), slug, fill=(255, 255, 255))

out = Path(r"C:\Users\KIUT\.gemini\antigravity\scratch\usta-xizmati\scripts\upgraded_6.png")
sheet.save(out, format="PNG")
print("Updated upgraded_6.png")
