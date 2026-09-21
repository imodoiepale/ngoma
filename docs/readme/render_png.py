"""Rasterize README diagrams to PNG. GitHub renders these; SVG stays as source."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "assets"
BG = (10, 10, 10)
PANEL = (28, 24, 18)
GOLD = (240, 215, 140)
GOLD_DIM = (201, 162, 39)
CREAM = (245, 240, 232)
MUTED = (168, 155, 124)
BODY = (217, 208, 190)
GREEN = (134, 239, 172)
GREEN_DK = (22, 101, 52)
RED = (252, 165, 165)
RED_DK = (127, 29, 29)
STROKE = (63, 58, 50)
YELLOW = (252, 211, 77)
YELLOW_DK = (133, 77, 14)


def font(size: int, bold: bool = False, serif: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if serif:
        names = (
            ("C:/Windows/Fonts/georgia.ttf", "C:/Windows/Fonts/georgiab.ttf"),
            ("C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/timesbd.ttf"),
        )
    else:
        names = (
            ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
            ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
            ("C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/calibrib.ttf"),
        )
    for regular, heavy in names:
        path = heavy if bold else regular
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def rounded(draw: ImageDraw.ImageDraw, xy, r: int, fill, outline=None, width: int = 2) -> None:
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


def text_center(draw, xy, text, fnt, fill) -> None:
    draw.text(xy, text, font=fnt, fill=fill, anchor="mm")


def wordmark() -> None:
    im = Image.new("RGB", (1440, 240), BG)
    d = ImageDraw.Draw(im)
    d.text((48, 70), "DIRECTOR", font=font(72, True, serif=True), fill=CREAM)
    d.text((52, 160), "OPEN CREATIVE STUDIO", font=font(22, bold=True), fill=GOLD_DIM)
    im.save(OUT / "wordmark.png", optimize=True)


def cost() -> None:
    im = Image.new("RGB", (2400, 720), BG)
    d = ImageDraw.Draw(im)
    rounded(d, (0, 0, 2399, 719), 36, BG)
    d.text((96, 56), "What 1,000 stills actually cost", font=font(44, True, serif=True), fill=CREAM)
    d.text(
        (96, 120),
        "Hosted credits expire. Open weights bill GPU seconds. Klein text-to-image: 45 images in 364.87 s = 444 / hour.",
        font=font(24),
        fill=MUTED,
    )
    d.text((96, 220), "Hosted flagship 4K  ~ $240", font=font(26, True), fill=RED)
    rounded(d, (96, 260, 2176, 316), 12, RED_DK)
    d.text((120, 274), "Nano Banana Pro class, about $0.24 / 4K still, credits reset monthly", font=font(22), fill=(254, 226, 226))
    d.text((96, 370), "Hosted daily stills  ~ $70", font=font(26, True), fill=YELLOW)
    rounded(d, (96, 410, 704, 466), 12, YELLOW_DK)
    d.text((120, 424), "Nano Banana 2, about $0.07 / still", font=font(22), fill=(254, 243, 199))
    d.text((96, 520), "This studio, open weights  ~ $4", font=font(26, True), fill=GREEN)
    rounded(d, (96, 560, 140, 616), 10, GREEN_DK)
    d.text(
        (160, 574),
        "FLUX.2 Klein on an A100, measured 444/h, about 2.3 GPU-h + load, $1.64/h planning rate",
        font=font(22),
        fill=(187, 247, 208),
    )
    im.save(OUT / "cost.png", optimize=True)


def stack() -> None:
    im = Image.new("RGB", (2400, 840), BG)
    d = ImageDraw.Draw(im)
    d.text((96, 56), "Four layers, each generated from the one below", font=font(44, True, serif=True), fill=CREAM)
    d.text((96, 120), "A capability is Ready, Needs setup, or a declared Gap. Nothing is faked.", font=font(24), fill=MUTED)
    rows = [
        ("Offers", "50 costed ideas, proposals, diagrams, brands/_business/ideas.yaml", GOLD, GOLD_DIM),
        ("Pipelines", "One *.studio.json template per idea, brands/_templates/workflows/", GOLD, GOLD_DIM),
        ("Steps", "Canvas catalogue, typed ports, consent and 18+ on the node", GREEN, (34, 197, 94)),
        ("Open backends", "ComfyUI graphs + port maps + model plan, local / pod / hosted peer", GREEN, (34, 197, 94)),
    ]
    y = 190
    for title, sub, title_c, stroke in rows:
        rounded(d, (96, y, 2304, y + 120), 20, PANEL, stroke, 3)
        d.text((140, y + 28), title, font=font(32, True), fill=title_c)
        d.text((140, y + 72), sub, font=font(22), fill=BODY)
        y += 150
    im.save(OUT / "stack.png", optimize=True)


def pipeline() -> None:
    im = Image.new("RGB", (2400, 840), BG)
    d = ImageDraw.Draw(im)
    d.text((96, 48), "From a sentence to a finished brand piece", font=font(44, True, serif=True), fill=CREAM)
    d.text(
        (96, 108),
        "Models make pictures. Code makes brands. Humans approve every spend and every post.",
        font=font(24),
        fill=MUTED,
    )
    steps = [
        ("1. Describe", "brief - song - calendar", GOLD, GOLD_DIM),
        ("2. Director", "profile + preset", GOLD, GOLD_DIM),
        ("3. Workflow", "steps - gaps - cost", GOLD, GOLD_DIM),
        ("4. Generate", "open weights or hosted", GREEN, (34, 197, 94)),
        ("5. Composite", "logo - type - contrast", GOLD, GOLD_DIM),
        ("6. Publish", "draft until yes", GREEN, (34, 197, 94)),
    ]
    x = 80
    y = 190
    w, h = 340, 160
    gap = 40
    for i, (title, sub, tc, stroke) in enumerate(steps):
        rounded(d, (x, y, x + w, y + h), 22, PANEL, stroke, 3)
        text_center(d, (x + w // 2, y + 62), title, font(26, True), tc)
        text_center(d, (x + w // 2, y + 104), sub, font(20), BODY)
        if i < len(steps) - 1:
            ax = x + w + 4
            d.line((ax, y + h // 2, ax + gap - 16, y + h // 2), fill=GOLD_DIM, width=4)
            d.polygon(
                [(ax + gap - 8, y + h // 2), (ax + gap - 22, y + h // 2 - 8), (ax + gap - 22, y + h // 2 + 8)],
                fill=GOLD_DIM,
            )
        x += w + gap
    panels = [
        (80, 400, 740, 780, GOLD, "Workspace", ["brand.yaml, palette, logo master", "owned / licensed / fictional refs", "rights, consent, 18+ flags"], "Any brand. Nothing in the pipeline is client-specific."),
        (780, 400, 1540, 780, GREEN, "Open GPU path", ["FLUX.2 Klein, Krea 2, Qwen Image", "WAN, LTX, SCAIL 2, H3 RefMod", "Your pod. Your LoRAs. Your policy."], "Measured: 444 Klein stills per A100 hour."),
        (1580, 400, 2320, 780, GOLD, "Hard gates", ["Dry-run by default, budget_usd = 0", "Queued is not success", "Composite the logo, never regenerate it"], "Agents create. Code validates. You approve."),
    ]
    for x0, y0, x1, y1, tc, title, lines, foot in panels:
        rounded(d, (x0, y0, x1, y1), 24, (20, 17, 13), STROKE, 2)
        d.text((x0 + 36, y0 + 36), title, font=font(28, True), fill=tc)
        yy = y0 + 100
        for line in lines:
            d.text((x0 + 36, yy), line, font=font(22), fill=BODY)
            yy += 40
        d.text((x0 + 36, y1 - 60), foot, font=font(20), fill=MUTED)
    im.save(OUT / "pipeline.png", optimize=True)


def architecture() -> None:
    im = Image.new("RGB", (2400, 960), BG)
    d = ImageDraw.Draw(im)
    d.text((96, 48), "System layout", font=font(44, True, serif=True), fill=CREAM)
    d.text(
        (96, 108),
        "Studio and author write studio.json. Engine routes. Hosted models sit beside the pod. Code composites. You approve.",
        font=font(24),
        fill=MUTED,
    )

    def box(xy, title, sub, stroke, tc):
        rounded(d, xy, 22, PANEL, stroke, 3)
        cx = (xy[0] + xy[2]) // 2
        cy = (xy[1] + xy[3]) // 2
        text_center(d, (cx, cy - 18), title, font(26, True), tc)
        text_center(d, (cx, cy + 22), sub, font(20), BODY)

    box((96, 190, 760, 350), "Studio canvas :3000", "packages/studio-ui", GOLD_DIM, GOLD)
    box((1640, 190, 2304, 350), "workflow_author / say", "packages/strategy, packages/engine", GOLD_DIM, GOLD)
    box((640, 430, 1760, 590), "Engine runner, ports, cost", "packages/engine - dry-run default, budget_usd cap", GOLD_DIM, GOLD)
    box((96, 710, 760, 870), "OpenRouter peer", "packages/image-router", (34, 197, 94), GREEN)
    box((820, 710, 1580, 870), "ComfyUI on RunPod", "comfy-client - COMPLETED with files only", (34, 197, 94), GREEN)
    box((1640, 710, 2304, 870), "Compositor + publish draft", "logo, type, contrast, sha256 sidecar", GOLD_DIM, GOLD)
    d.line((428, 350, 428, 430), fill=GOLD_DIM, width=3)
    d.line((1972, 350, 1972, 430), fill=GOLD_DIM, width=3)
    d.line((1200, 590, 1200, 710), fill=GOLD_DIM, width=3)
    d.line((640, 510, 428, 510), fill=GOLD_DIM, width=3)
    d.line((428, 510, 428, 710), fill=GOLD_DIM, width=3)
    d.line((1760, 510, 1972, 510), fill=GOLD_DIM, width=3)
    d.line((1972, 510, 1972, 710), fill=GOLD_DIM, width=3)
    im.save(OUT / "architecture.png", optimize=True)


def who() -> None:
    im = Image.new("RGB", (2400, 1040), BG)
    d = ImageDraw.Draw(im)
    d.text((96, 48), "Who this is for", font=font(44, True, serif=True), fill=CREAM)
    d.text(
        (96, 112),
        "Eight families. Fifty costed offers. One studio. The pipeline does not care which brand you open.",
        font=font(24),
        fill=MUTED,
    )
    cards = [
        (80, 190, "Agencies and SMMs", ["1,000 on-brand stills a day.", "Carousels from one product photo.", "Thumbnails, covers, retainers."], "V01, V02, V08", GOLD, GREEN, STROKE),
        (650, 190, "Local businesses", ["Restaurants, real estate, shops.", "WhatsApp Status every morning.", "Sheng and Kiswahili captions."], "V03, V04, V06, U04", GOLD, GREEN, STROKE),
        (1220, 190, "Fashion and D2C", ["Every SKU on a fictional model.", "Wardrobe swap, try-on, lookbooks.", "Identity locked across a batch."], "V05, P07, P02", GOLD, GREEN, STROKE),
        (1790, 190, "Artists and labels", ["Full-length music videos.", "Spotify Canvas, VJ loops.", "Artist digital doubles."], "M01-M08", GOLD, GREEN, STROKE),
        (80, 560, "UGC / performance", ["Ad packs, hook tests, dubs.", "TikTok Shop product clips.", "App-install demo ads."], "U01-U07", GOLD, GREEN, STROKE),
        (650, 560, "Persona operators", ["Own an AI influencer.", "Character boards and LoRAs.", "Licensing and greetings."], "P01-P09, S01", GOLD, GREEN, STROKE),
        (1220, 560, "Studios and agencies", ["Image API, brand engine.", "Workflow packs, bootcamps.", "Product photography replacement."], "A01-A03, E01-E05, S02-S08", GOLD, GREEN, STROKE),
        (1790, 560, "18+ fiction only", ["Adult fictional personas.", "Separate entity and payments.", "Never on client brand infra."], "X01, X02, gated", RED, RED, RED_DK),
    ]
    for x, y, title, lines, tag, tc, tagc, stroke in cards:
        rounded(d, (x, y, x + 530, y + 340), 24, PANEL, stroke, 2)
        d.text((x + 36, y + 36), title, font=font(28, True), fill=tc)
        yy = y + 100
        for line in lines:
            d.text((x + 36, yy), line, font=font(22), fill=BODY)
            yy += 40
        d.text((x + 36, y + 280), tag, font=font(20), fill=tagc)
    im.save(OUT / "who.png", optimize=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    wordmark()
    cost()
    stack()
    pipeline()
    architecture()
    who()
    for name in ("wordmark.png", "cost.png", "stack.png", "pipeline.png", "architecture.png", "who.png"):
        p = OUT / name
        print(f"{name} {p.stat().st_size} bytes")
