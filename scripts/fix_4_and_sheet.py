import httpx
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from fetch_wiki_lead_photos import save_as_card_png, get_wiki_lead_image, ACCENT_COLORS, DOWNLOAD_DIR, SERVICES_DIR

FIXES = {
    "kafelchi": ["Porcelain tile", "Ceramic tile", "Mosaic"],
    "mebelchi": ["Kitchen cabinet", "Cabinetry", "Wardrobe"],
    "deraza-rom-eshik": ["Window", "Door", "Patio door"],
    "klining-dezinfeksiya": ["Vacuum cleaner", "Carpet cleaning", "Pressure washer"],
}

headers = {"User-Agent": "UstaBorServiceCatalog/1.0 (dev@ustabor.local)"}
with httpx.Client(headers=headers, follow_redirects=True) as client:
    for slug, titles in FIXES.items():
        for t in titles:
            url = get_wiki_lead_image(client, t)
            if url:
                r = client.get(url, timeout=30)
                r.raise_for_status()
                raw = DOWNLOAD_DIR / f"{slug}_fix.jpg"
                raw.write_bytes(r.content)
                save_as_card_png(raw, SERVICES_DIR / f"{slug}.png", ACCENT_COLORS[slug])
                print(f"[FIX] {slug} ({t}) <- {url}")
                break

# Build 6x5 contact sheet of all 30 images
pngs = sorted(SERVICES_DIR.glob("*.png"))
cols, rows = 5, 6
thumb_w, thumb_h = 320, 240
sheet = Image.new("RGB", (cols * thumb_w, rows * thumb_h), (15, 23, 42))
draw = ImageDraw.Draw(sheet)

for idx, p in enumerate(pngs[:30]):
    r, c = divmod(idx, cols)
    with Image.open(p) as im:
        im_small = im.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(im_small, (c * thumb_w, r * thumb_h))
    draw.rectangle([(c * thumb_w, r * thumb_h), (c * thumb_w + 200, r * thumb_h + 24)], fill=(15, 23, 42))
    draw.text((c * thumb_w + 6, r * thumb_h + 6), p.stem, fill=(255, 255, 255))

out_sheet = Path(r"C:\Users\KIUT\.gemini\antigravity\scratch\usta-xizmati\scripts\contact_sheet.png")
sheet.save(out_sheet, format="PNG")
print(f"Contact sheet saved: {out_sheet} ({len(pngs)} images)")
