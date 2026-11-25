import httpx
from pathlib import Path
from PIL import Image, ImageDraw
from fetch_wiki_lead_photos import save_as_card_png, get_wiki_lead_image, ACCENT_COLORS, DOWNLOAD_DIR, SERVICES_DIR

BRAIN_DIR = Path(r"C:\Users\KIUT\.gemini\antigravity\brain\7fc7f266-c40d-4d8b-b773-fc8d7791aa1c")
WOOD_SRC = BRAIN_DIR / "artisan_wood_brick_services_card_1795597759723.jpg"

# Door & window crop from bespoke workshop image
with Image.open(WOOD_SRC) as im:
    w, h = im.size
    c = im.crop((int(0.18 * w), 0, int(0.68 * w), int(0.75 * h)))
    tmp = DOWNLOAD_DIR / "door_crop.jpg"
    c.save(tmp, format="JPEG", quality=95)
save_as_card_png(tmp, SERVICES_DIR / "deraza-rom-eshik.png", ACCENT_COLORS["deraza-rom-eshik"])

# Cleaning photo
headers = {"User-Agent": "UstaBorServiceCatalog/1.0 (dev@ustabor.local)"}
with httpx.Client(headers=headers, follow_redirects=True) as client:
    for t in ["Pressure washing", "Carpet cleaning", "Disinfectant"]:
        u = get_wiki_lead_image(client, t)
        if u:
            r = client.get(u, timeout=30)
            r.raise_for_status()
            tmp2 = DOWNLOAD_DIR / "clean_pw.jpg"
            tmp2.write_bytes(r.content)
            save_as_card_png(tmp2, SERVICES_DIR / "klining-dezinfeksiya.png", ACCENT_COLORS["klining-dezinfeksiya"])
            print(f"[OK] klining-dezinfeksiya ({t}) <- {u}")
            break

# Rebuild 5x6 contact sheet of all 30 service images
pngs = sorted(SERVICES_DIR.glob("*.png"))
cols, rows = 5, 6
thumb_w, thumb_h = 320, 240
sheet = Image.new("RGB", (cols * thumb_w, rows * thumb_h), (15, 23, 42))
draw = ImageDraw.Draw(sheet)

for idx, p in enumerate(pngs[:30]):
    r, c = divmod(idx, cols)
    with Image.open(p) as im:
        sheet.paste(im.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS), (c * thumb_w, r * thumb_h))
    draw.rectangle([(c * thumb_w, r * thumb_h), (c * thumb_w + 200, r * thumb_h + 24)], fill=(15, 23, 42))
    draw.text((c * thumb_w + 6, r * thumb_h + 6), p.stem, fill=(255, 255, 255))

out_sheet = Path(r"C:\Users\KIUT\.gemini\antigravity\scratch\usta-xizmati\scripts\contact_sheet.png")
sheet.save(out_sheet, format="PNG")
print(f"Rebuilt contact_sheet.png ({len(pngs)} images)")
