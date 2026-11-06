"""Builds the Neon Pulse watchface for the Mi Band 6 (152x486): a folder with watchface.json and numbered PNGs
for pack_face.py, plus a preview sheet rendered in Python from the same layout.

v2: temperature instead of steps; the dot under the clock takes its color from the heart rate (HeartProgress picks one of
11 dots) and a ring around it pulses on a fixed rhythm (Other.Animation)."""
import json
import os
import shutil
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "neon_face")
FONT = "C:/Windows/Fonts/bahnschrift.ttf"

W, H = 152, 486
BLACK = (0, 0, 0)
LIME = (0xC6, 0xFF, 0x3D)
WHITE = (0xF2, 0xF2, 0xF2)
CYAN = (0x3D, 0xE0, 0xFF)
MAGENTA = (0xFF, 0x3D, 0xD0)
ORANGE = (0xFF, 0x7A, 0x3D)
RED = (0xFF, 0x3D, 0x6E)
LOW = (0xFF, 0x3D, 0x6E)
AMBER = (0xFF, 0xB0, 0x3D)
TRACK = (0x26, 0x26, 0x26)

# the dot: cold at rest, through lime and amber, to hot at the top of the range (index = progress / 10)
DOT_COLORS = [(0x3D, 0x5B, 0xFF), (0x3D, 0xA5, 0xFF), CYAN, (0x3D, 0xFF, 0xB0), LIME, (0xFF, 0xE0, 0x3D),
              AMBER, ORANGE, RED, MAGENTA, (0xFF, 0xFF, 0xFF)]

images = []  # RGBA images; their position in the list is their id


def add(img, see_through=False):
    """Stores the image and returns its id. A see-through image is light on black: its brightness becomes its alpha, so
    that it blends over whatever is behind it (the dot and the ring)."""
    rgb = img.convert("RGB")
    if see_through:
        px = rgb.load()
        out = Image.new("RGBA", rgb.size)
        po = out.load()
        for y in range(rgb.height):
            for x in range(rgb.width):
                r, g, b = px[x, y]
                a = max(r, g, b)
                po[x, y] = (0, 0, 0, 0) if a == 0 else (r * 255 // a, g * 255 // a, b * 255 // a, a)
        images.append(out)
    else:
        images.append(rgb.convert("RGBA"))
    return len(images) - 1


def font(size, style="Bold Condensed"):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_name(style)
    return f


def fit_size(target_height, style):
    """Font size at which the digit 0 is target_height tall."""
    f = font(100, style)
    box = f.getbbox("0", anchor="ls")
    return round(100 * target_height / (box[3] - box[1]))


def glow_text(img, xy, text, f, color, glow=0.0, radius=4, anchor="ls"):
    if glow > 0:
        layer = Image.new("L", img.size, 0)
        ImageDraw.Draw(layer).text(xy, text, font=f, fill=255, anchor=anchor)
        layer = layer.filter(ImageFilter.GaussianBlur(radius))
        tint = Image.new("RGB", img.size, color)
        img.paste(tint, (0, 0), layer.point(lambda v: int(v * glow)))
    ImageDraw.Draw(img).text(xy, text, font=f, fill=color, anchor=anchor)


def digit_set(w, h, glyph_h, color, glow=0.0, radius=4, style="Bold Condensed"):
    size = fit_size(glyph_h, style)
    f = font(size, style)
    first = len(images)
    baseline = (h + glyph_h) // 2
    for d in "0123456789":
        img = Image.new("RGB", (w, h), BLACK)
        glow_text(img, (w / 2, baseline), d, f, color, glow, radius, anchor="ms")
        add(img)
    return first


def label(text, w, h, glyph_h, color, align="left", style="Bold"):
    f = font(fit_size(glyph_h, style), style)
    img = Image.new("RGB", (w, h), BLACK)
    base = (h + glyph_h) // 2
    x, anchor = (0, "ls") if align == "left" else (w, "rs")
    ImageDraw.Draw(img).text((x, base), text, font=f, fill=color, anchor=anchor)
    return add(img)


SS = 4  # icons are drawn 4x and scaled down for smooth edges


def icon(draw_fn, size=22):
    big = Image.new("RGB", (size * SS, size * SS), BLACK)
    draw_fn(ImageDraw.Draw(big), size * SS)
    return add(big.resize((size, size), Image.LANCZOS))


def draw_thermometer(d, s):
    u = s / 22
    d.rounded_rectangle([8.2 * u, 1.5 * u, 13.8 * u, 15 * u], radius=2.8 * u, outline=ORANGE, width=int(1.8 * u))
    d.ellipse([5.2 * u, 12 * u, 16.8 * u, 23.6 * u], fill=ORANGE)
    d.rounded_rectangle([9.9 * u, 6 * u, 12.1 * u, 16 * u], radius=1 * u, fill=ORANGE)
    for y in (4.5, 8, 11.5):  # scale ticks
        d.line([(15.2 * u, y * u), (18 * u, y * u)], fill=ORANGE, width=int(1.3 * u))


def draw_heart(d, s):
    u = s / 22
    d.ellipse([1 * u, 3 * u, 11.6 * u, 13.6 * u], fill=RED)
    d.ellipse([10.4 * u, 3 * u, 21 * u, 13.6 * u], fill=RED)
    d.polygon([(1.7 * u, 10 * u), (20.3 * u, 10 * u), (11 * u, 20.5 * u)], fill=RED)
    d.line([(3 * u, 11 * u), (7.5 * u, 11 * u), (9.3 * u, 7.4 * u), (12 * u, 14.4 * u), (13.7 * u, 11 * u), (19 * u, 11 * u)],
           fill=BLACK, width=int(1.6 * u))


def draw_battery(d, s):
    u = s / 22
    d.rounded_rectangle([1 * u, 5 * u, 18 * u, 17 * u], radius=2.4 * u, outline=CYAN, width=int(1.8 * u))
    d.rectangle([19.2 * u, 8.6 * u, 21 * u, 13.4 * u], fill=CYAN)
    d.rounded_rectangle([3.8 * u, 7.8 * u, 14.2 * u, 14.2 * u], radius=1 * u, fill=CYAN)


def bar_set(color_for, w=124, h=8):
    """11 images of a rounded bar filled 0, 10 ... 100 percent."""
    first = len(images)
    for k in range(11):
        sc = 4
        big = Image.new("RGB", (w * sc, h * sc), BLACK)
        d = ImageDraw.Draw(big)
        d.rounded_rectangle([0, 0, w * sc - 1, h * sc - 1], radius=h * sc // 2, fill=TRACK)
        if k:
            fill = max(h * sc, round(w * sc * k / 10))
            d.rounded_rectangle([0, 0, fill - 1, h * sc - 1], radius=h * sc // 2, fill=color_for(k))
        add(big.resize((w, h), Image.LANCZOS))
    return first


DOT_BOX = 28  # the dot and the ring around it share one square, centered under the clock
DOT_CENTER = (76, 290)
DOT_XY = (DOT_CENTER[0] - DOT_BOX // 2, DOT_CENTER[1] - DOT_BOX // 2)
RING_BOX = 40
RING_XY = (DOT_CENTER[0] - RING_BOX // 2, DOT_CENTER[1] - RING_BOX // 2)
RING_FRAMES = 10


def dot_set():
    """11 dots, one per tenth of the heart-rate range, each with a soft glow in its own color."""
    first = len(images)
    c = DOT_BOX / 2
    for color in DOT_COLORS:
        img = Image.new("RGB", (DOT_BOX, DOT_BOX), BLACK)
        layer = Image.new("L", img.size, 0)
        ImageDraw.Draw(layer).ellipse([c - 5, c - 5, c + 5, c + 5], fill=255)
        glow = layer.filter(ImageFilter.GaussianBlur(3.2))
        img.paste(Image.new("RGB", img.size, color), (0, 0), glow.point(lambda v: min(255, int(v * 1.15))))
        sc = 4
        big = Image.new("L", (DOT_BOX * sc, DOT_BOX * sc), 0)
        ImageDraw.Draw(big).ellipse([(c - 5) * sc, (c - 5) * sc, (c + 5) * sc, (c + 5) * sc], fill=255)
        core = big.resize((DOT_BOX, DOT_BOX), Image.LANCZOS)
        img.paste(Image.new("RGB", img.size, color), (0, 0), core)
        add(img, see_through=True)
    return first


def ring_set():
    """A ring that grows from the dot and fades, white, with a transparent middle so the dot stays visible."""
    first = len(images)
    c = RING_BOX / 2
    for k in range(RING_FRAMES):
        t = k / (RING_FRAMES - 1)
        radius = 8 + 11 * t
        strength = (1 - t) ** 1.3
        sc = 4
        big = Image.new("L", (RING_BOX * sc, RING_BOX * sc), 0)
        w = (2.4 - 1.0 * t) * sc
        ImageDraw.Draw(big).ellipse([(c - radius) * sc, (c - radius) * sc, (c + radius) * sc, (c + radius) * sc],
                                    outline=255, width=max(1, round(w)))
        mask = big.resize((RING_BOX, RING_BOX), Image.LANCZOS).point(lambda v: int(v * strength))
        img = Image.new("RGB", (RING_BOX, RING_BOX), BLACK)
        img.paste(Image.new("RGB", img.size, (0xE8, 0xFF, 0xB0)), (0, 0), mask)
        add(img, see_through=True)
    return first


def background():
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)
    # hairline between the clock and the data, fading toward both sides; the dot sits in the middle of it
    y = DOT_CENTER[1]
    for x in range(14, 138):
        if abs(x - 76) < 14:
            continue
        t = 1 - abs(x - 76) / 62
        d.point((x, y), fill=tuple(int(v * (0.10 + 0.9 * t * t)) for v in LIME))
    return add(img)


# ---------------------------------------------------------------- assets
bg_id = background()

BIG_W, BIG_H, BIG_GLYPH = 68, 104, 80
hours = digit_set(BIG_W, BIG_H, BIG_GLYPH, LIME, glow=0.75, radius=5)
minutes = digit_set(BIG_W, BIG_H, BIG_GLYPH, WHITE, glow=0.35, radius=5)

SM_W, SM_H, SM_GLYPH = 17, 28, 20
MD_W, MD_H, MD_GLYPH = 21, 36, 27
date_digits = digit_set(SM_W, SM_H, SM_GLYPH, MAGENTA, style="Bold")
battery_digits = digit_set(SM_W, SM_H, SM_GLYPH, CYAN, style="Bold")
temp_digits = digit_set(MD_W, MD_H, MD_GLYPH, ORANGE, style="Bold")
pulse_digits = digit_set(MD_W, MD_H, MD_GLYPH, RED, style="Bold")

temp_minus = label("-", MD_W, MD_H, MD_GLYPH, ORANGE, align="left", style="Bold")
temp_degree = label("\u00b0", 14, MD_H, MD_GLYPH, ORANGE, align="left", style="Bold")
pulse_nodata = label("--", 40, MD_H, MD_GLYPH, (0x7A, 0x1E, 0x35), align="right", style="Bold")
percent = label("%", SM_W + 3, SM_H, SM_GLYPH, CYAN, align="left", style="Bold")

days_it = ["LUN", "MAR", "MER", "GIO", "VEN", "SAB", "DOM"]
weekdays = [label(t, 56, 26, 20, MAGENTA, align="left", style="Bold") for t in days_it]

thermo_icon = icon(draw_thermometer)
heart_icon = icon(draw_heart)
battery_icon = icon(draw_battery)


def battery_color(k):
    return LOW if k <= 2 else AMBER if k <= 4 else CYAN


battery_bar = bar_set(battery_color)
dots = dot_set()
rings = ring_set()

# ---------------------------------------------------------------- layout
ROW_TEMP, ROW_HEART, ROW_BATT = 304, 350, 402


def num(x0, y0, x1, y1, first, spacing=2, align="Right"):
    return {"TopLeftX": x0, "TopLeftY": y0, "BottomRightX": x1, "BottomRightY": y1, "Alignment": align,
            "SpacingX": spacing, "SpacingY": 0, "ImageIndex": first, "ImagesCount": 10}


def rng(x, y, first, count):
    return {"X": x, "Y": y, "ImageIndex": first, "ImagesCount": count}


def pic(x, y, idx):
    return {"X": x, "Y": y, "ImageIndex": idx}


layout = {
    "Time": {
        "Hours": {"Tens": rng(4, 58, hours, 10), "Ones": rng(80, 58, hours, 10)},
        "Minutes": {"Tens": rng(4, 170, minutes, 10), "Ones": rng(80, 170, minutes, 10)},
        "DrawingOrder": False,
    },
    "Date": {
        "MonthAndDayAndYear": {"Separate": {"Day": num(86, 31, 136, 59, date_digits)}},
        "ENWeekDays": rng(16, 32, weekdays[0], 7),
    },
    "Activity": {
        "Pulse": {"Number": num(44, ROW_HEART, 138, ROW_HEART + MD_H, pulse_digits), "NoDataImageIndex": pulse_nodata},
        "UnknownV7": 0,
    },
    "Weather": {
        "Temperature": {
            "Current": {
                "Number": num(44, ROW_TEMP, 138, ROW_TEMP + MD_H, temp_digits),
                "MinusImageIndex": temp_minus,
                "SuffixImageIndex": temp_degree,
            },
        },
    },
    "Battery": {
        "BatteryText": {"Number": num(40, ROW_BATT, 138, ROW_BATT + SM_H, battery_digits), "SuffixImageIndex": percent},
        "BatteryIcon": rng(14, ROW_BATT + 34, battery_bar, 11),
    },
    "HeartProgress": {"LineScale": rng(DOT_XY[0], DOT_XY[1], dots, 11)},
    "Other": {
        "Animation": {
            "AnimationImages": rng(RING_XY[0], RING_XY[1], rings, RING_FRAMES),
            "Speed": 10,
            "RepeatCount": 8,
        },
    },
}

# the icons live in the background, so that they need no drawing slot of their own
bg = images[bg_id].convert("RGB")
for y0, idx in ((ROW_TEMP + 7, thermo_icon), (ROW_HEART + 7, heart_icon), (ROW_BATT + 3, battery_icon)):
    bg.paste(images[idx].convert("RGB"), (13, y0))
images[bg_id] = bg.convert("RGBA")


# ---------------------------------------------------------------- preview render (same positions as the band uses)
def compose(hh=10, mm=9, weekday=4, day=30, temp=21, pulse=72, pulse_pct=40, battery=80, ring=None):
    img = images[bg_id].convert("RGB")

    def put(idx, x, y):
        im = images[idx]
        img.paste(im.convert("RGB"), (x, y), im.getchannel("A"))

    def text(spec, value, minus=None, suffix=None):
        ids = [minus if c == "-" else spec["ImageIndex"] + int(c) for c in str(value)]
        if suffix is not None:
            ids.append(suffix)
        total = sum(images[i].width for i in ids) + spec["SpacingX"] * (len(ids) - 1)
        x = spec["BottomRightX"] - total
        for i in ids:
            y = round((spec["TopLeftY"] + spec["BottomRightY"]) / 2 - images[i].height / 2)
            put(i, x, y)
            x += images[i].width + spec["SpacingX"]

    t = layout["Time"]
    put(t["Hours"]["Tens"]["ImageIndex"] + hh // 10, t["Hours"]["Tens"]["X"], t["Hours"]["Tens"]["Y"])
    put(t["Hours"]["Ones"]["ImageIndex"] + hh % 10, t["Hours"]["Ones"]["X"], t["Hours"]["Ones"]["Y"])
    put(t["Minutes"]["Tens"]["ImageIndex"] + mm // 10, t["Minutes"]["Tens"]["X"], t["Minutes"]["Tens"]["Y"])
    put(t["Minutes"]["Ones"]["ImageIndex"] + mm % 10, t["Minutes"]["Ones"]["X"], t["Minutes"]["Ones"]["Y"])
    wd = layout["Date"]["ENWeekDays"]
    put(wd["ImageIndex"] + weekday, wd["X"], wd["Y"])
    text(layout["Date"]["MonthAndDayAndYear"]["Separate"]["Day"], day)
    cur = layout["Weather"]["Temperature"]["Current"]
    text(cur["Number"], temp, cur["MinusImageIndex"], cur["SuffixImageIndex"])
    text(layout["Activity"]["Pulse"]["Number"], pulse)
    text(layout["Battery"]["BatteryText"]["Number"], battery, suffix=layout["Battery"]["BatteryText"]["SuffixImageIndex"])
    r = layout["HeartProgress"]["LineScale"]
    put(r["ImageIndex"] + round(pulse_pct / 100 * (r["ImagesCount"] - 1)), r["X"], r["Y"])
    r = layout["Battery"]["BatteryIcon"]
    put(r["ImageIndex"] + round(battery / 100 * (r["ImagesCount"] - 1)), r["X"], r["Y"])
    if ring is not None:
        a = layout["Other"]["Animation"]["AnimationImages"]
        put(a["ImageIndex"] + ring, a["X"], a["Y"])
    return img


def round_corners(img):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=img.width // 2, fill=255)
    out = Image.new("RGB", img.size, (24, 24, 24))
    out.paste(img, (0, 0), mask)
    return out


if __name__ == "__main__":
    scratch = sys.argv[1] if len(sys.argv) > 1 else HERE
    samples = (
        compose(ring=3),
        compose(hh=7, mm=45, weekday=0, day=3, temp=-4, pulse=0, pulse_pct=0, battery=15, ring=7),
        compose(hh=23, mm=58, weekday=6, day=28, temp=31, pulse=148, pulse_pct=95, battery=100, ring=0),
        compose(hh=14, mm=30, weekday=2, day=12, temp=12, pulse=96, pulse_pct=60, battery=47, ring=5),
    )
    sheet = Image.new("RGB", (W * 4 + 50, H + 20), (24, 24, 24))
    for i, s in enumerate(samples):
        sheet.paste(round_corners(s), (10 + i * (W + 10), 10))
    sheet.save(os.path.join(scratch, "face_sheet.png"))
    # the dot in its eleven colors, with the ring frames beside it
    strip = Image.new("RGB", (11 * 34 + 10, 44 * 2 + 14), (0, 0, 0))
    for k in range(11):
        im = images[dots + k]
        strip.paste(im.convert("RGB"), (5 + k * 34, 4), im.getchannel("A"))
    for k in range(RING_FRAMES):
        im = images[rings + k]
        strip.paste(im.convert("RGB"), (5 + k * 34 - 3, 50), im.getchannel("A"))
    strip = strip.resize((strip.width * 3, strip.height * 3), Image.NEAREST)
    strip.save(os.path.join(scratch, "dot_strip.png"))

    # the community face keeps its preview as a 152x229 picture placed at (21, 30)
    preview_id = add(samples[0].crop((0, 0, W, 229)))
    layout["Background"] = {
        "Image": pic(0, 0, bg_id),
        "PreviewEN": pic(21, 30, preview_id),
        "PreviewCN": pic(21, 30, preview_id),
        "PreviewCN2": pic(21, 30, preview_id),
    }

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    for i, im in enumerate(images):
        im.save(os.path.join(OUT, f"{i}.png"))
    with open(os.path.join(OUT, "watchface.json"), "w") as fh:
        json.dump(layout, fh, indent=1)
    print("images", len(images), "ids", dict(hours=hours, minutes=minutes, dots=dots, rings=rings, bg=bg_id, preview=preview_id))
