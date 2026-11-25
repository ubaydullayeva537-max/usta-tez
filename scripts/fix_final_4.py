import httpx
from pathlib import Path
from PIL import Image, ImageDraw
from fetch_wiki_lead_photos import save_as_card_png, get_wiki_lead_image, ACCENT_COLORS, DOWNLOAD_DIR, SERVICES_DIR

BRAIN_DIR = Path(r"C:\Users\KIUT\.gemini\antigravity\brain\7fc7f266-c40d-4d8b-b773-fc8d7791aa1c")
HOME_SRC = BRAIN_DIR / "home_service_card_1795597760325.jpg"

# Fix swapped crops: breaker panel on left (elektrik), AC installation on right (konditsioner)
with Image.open(HOME_SRC) as im:
    w, h = im.size
    elec_crop = im.crop((0, 0, int(0.62 * w), int(0.72 * h)))
    ac_crop = im.crop((int(0.32 * w), 0, w, int(0.72 * h)))
    t_e = DOWNLOAD_DIR / "elec_fix.jpg"
    t_a = DOWNLOAD_DIR / "ac_fix.jpg"
    elec_crop.save(t_e, format="JPEG", quality=95)
    ac_crop.save(t_a, format="JPEG", quality=95)

save_as_card_png(t_e, SERVICES_DIR / "elektrik.png", ACCENT_COLORS["elektrik"])
save_as_card_png(t_a, SERVICES_DIR / "konditsioner.png", ACCENT_COLORS["konditsioner"])

headers = {"User-Agent": "UstaBorServiceCatalog/1.0 (dev@ustabor.local)"}
with httpx.Client(headers=headers, follow_redirects=True) as client:
    for slug, titles in {
        "bogbon-landshaft": ["Lawn mower", "English garden", "Hedge (barrier)"],
        "klining-dezinfeksiya": ["Housekeeping", "Janitor", "Mop"],
    }.items():
        for t in titles:
            u = get_wiki_lead_image(client, t)
            if u:
                r = client.get(u, timeout=30)
                r.raise_for_status()
                raw = DOWNLOAD_DIR / f"{slug}_final.jpg"
                raw.write_bytes(r.content)
                save_as_card_png(raw, SERVICES_DIR / f"{slug}.png", ACCENT_COLORS[slug])
                print(f"[OK] {slug} ({t}) <- {u}")
                break

sheet = Image.new("RGB", (2 * 400, 2 * 300), (15, 23, 42))
draw = ImageDraw.Draw(sheet)
for idx, slug in enumerate(["elektrik", "konditsioner", "bogbon-landshaft", "klining-dezinfeksiya"]):
    r, c = divmod(idx, 2)
    with Image.open(SERVICES_DIR / f"{slug}.png") as im:
        sheet.paste(im.resize((400, 300), Image.Resampling.LANCZOS), (c * 400, r * 300))
    draw.rectangle([(c * 400, r * 300), (c * 400 + 200, r * 300 + 26)], fill=(15, 23, 42))
    draw.text((c * 400 + 8, r * 300 + 6), slug, fill=(255, 255, 255))

out = Path(r"C:\Users\KIUT\.gemini\antigravity\scratch\usta-xizmati\scripts\upgraded_4.png")
sheet.save(out, format="PNG")
print("Saved upgraded_4.png")
