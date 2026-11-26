import base64
import io
import json
import shutil
from pathlib import Path
from PIL import Image

ROOT = Path(r"C:\Users\KIUT\.gemini\antigravity\scratch\usta-xizmati")
IMAGES_DIR = ROOT / "app" / "static" / "images"
SERVICES_DIR = IMAGES_DIR / "services"
PUBLIC_STATIC = ROOT / "public" / "static"

# 1. Copy app/static -> public/static for Vercel CDN static serving
if PUBLIC_STATIC.exists():
    shutil.rmtree(PUBLIC_STATIC)
shutil.copytree(ROOT / "app" / "static", PUBLIC_STATIC)
# Remove any local uploaded test files from public/static/uploads
uploads_pub = PUBLIC_STATIC / "uploads"
if uploads_pub.exists():
    for f in uploads_pub.iterdir():
        if f.name != ".gitkeep":
            f.unlink()

# 2. Generate compact base64 JPEG thumbnails for standalone index.html fallback
def encode_thumb(path: Path, size: tuple[int, int], quality: int = 72) -> str:
    with Image.open(path) as im:
        im = im.convert("RGB")
        im = im.resize(size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"

embedded = {}
hero_path = IMAGES_DIR / "hero.jpg"
if hero_path.exists():
    embedded["hero"] = encode_thumb(hero_path, (960, 540), quality=72)

for png in sorted(SERVICES_DIR.glob("*.png")):
    embedded[png.stem] = encode_thumb(png, (400, 300), quality=72)

out_json = ROOT / "scripts" / "embedded_images.json"
out_json.write_text(json.dumps(embedded, ensure_ascii=False), encoding="utf-8")
total_kb = out_json.stat().st_size / 1024
print(f"Copied public/static and built {len(embedded)} embedded thumbnails ({total_kb:.1f} KB)")
