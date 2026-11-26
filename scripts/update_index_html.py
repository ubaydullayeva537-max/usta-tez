from pathlib import Path

ROOT = Path(r"C:\Users\KIUT\.gemini\antigravity\scratch\usta-xizmati")
html_path = ROOT / "index.html"
html = html_path.read_text(encoding="utf-8")

# 1. Hero fallback
html = html.replace(
    '<img src="./app/static/images/hero.jpg" alt="Usta xizmati" class="hero-bg" onerror="this.style.display=\'none\'" />',
    '<img id="heroImg" src="./app/static/images/hero.jpg" alt="Usta xizmati" class="hero-bg" onerror="this.onerror=null;if(window.EMBEDDED_IMAGES&&EMBEDDED_IMAGES.hero)this.src=EMBEDDED_IMAGES.hero;" />'
)

# 2. Source filter in admin orders
if 'id="admOrderFilterSource"' not in html:
    html = html.replace(
        '<select id="admOrderFilterStatus"',
        '<select id="admOrderFilterSource" style="padding:7px 11px;border:1px solid var(--border);border-radius:9px;font-size:0.82rem;" onchange="renderAdminOrders()">'
        '<option value="all">Sayt + Telegram</option>'
        '<option value="web">🌐 Faqat Sayt</option>'
        '<option value="telegram">🤖 Faqat Telegram</option>'
        '</select>\n                <select id="admOrderFilterStatus"'
    )

marker = '    const LS_KEY = "ustabor_standalone_store_v1";'
head = html[:html.index(marker)]
embedded_json = (ROOT / "scripts" / "embedded_images.json").read_text(encoding="utf-8")
tail = (ROOT / "scripts" / "index_tail.js").read_text(encoding="utf-8")

inject = f"    const EMBEDDED_IMAGES = {embedded_json};\n    window.EMBEDDED_IMAGES = EMBEDDED_IMAGES;\n\n"
html_path.write_text(head + inject + tail, encoding="utf-8")
print(f"Successfully updated index.html ({html_path.stat().st_size / 1024:.1f} KB)")
