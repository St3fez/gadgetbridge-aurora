"""Packs wf/neon_face (watchface.json + N.png) into a Mi Band 6 watchface .bin (UIHH, header byte 4 = 1).

Written from the file layout described in the sources of the open-source watchface-js project (read, not run):
header | parameter info | parameters | image offsets | images. The parameter names and the header template come
from that project's UIHH_MIBAND.json, which is data only."""
import json
import os
import struct
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = json.load(open(os.path.join(HERE, "node_modules/watchface-js/src/watchFaceBinTools/models/fileTypes/UIHH_MIBAND.json")))
HEADER = bytes(SPEC["header"])

ALIGN = {"Left": 2, "Right": 4, "HCenter": 8, "Top": 16, "Bottom": 32, "VCenter": 64, "TopLeft": 18, "BottomLeft": 34,
         "CenterLeft": 66, "TopRight": 20, "BottomRight": 36, "CenterRight": 68, "TopCenter": 24, "BottomCenter": 40,
         "Center": 72}


def by_name(desc):
    """{"3:Time": {...}} -> {"Time": (3, {...})}; leaves literal type names alone."""
    if not isinstance(desc, dict):
        return desc
    out = {}
    for key, value in desc.items():
        ident, name = key.split(":")
        out[name] = (int(ident), by_name(value))
    return out


ROOT = by_name(SPEC["parameters"])
TYPES = {name: by_name(desc) for name, desc in SPEC["types"].items()}


def literal(value, kind):
    if kind in ("int", "imgid", "float"):
        assert isinstance(value, int), (value, kind)
        return value
    if kind == "bool":
        return int(bool(value))
    if kind == "alignment":
        return ALIGN[value]
    if kind == "color":
        return int(value, 16)
    raise ValueError(kind)


def to_ids(value, desc):
    if not isinstance(value, dict):
        return literal(value, desc)
    out = {}
    for name, child in value.items():
        ident, kind = desc[name]
        if isinstance(kind, str) and kind in TYPES:
            kind = TYPES[kind]
        out[ident] = to_ids(child, kind)
    return out


def varint(n):
    assert n >= 0
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        if n:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def encode(params):
    out = bytearray()
    for key in sorted(params):
        value = params[key]
        if isinstance(value, dict):
            children = encode(value)
            out += varint((key << 3) | 2) + varint(len(children)) + children
        else:
            out += varint(key << 3) + varint(value)
    return bytes(out)


def bgr565(r, g, b):
    return ((b & 0xF8) << 8) | ((g & 0xFC) << 3) | ((r & 0xF8) >> 3)


def encode_image(png_path):
    """The two formats the community watchface uses: 16-bit BGR565 little endian (format 0x08) for opaque images, and
    24-bit (format 0x1B) for the others: one alpha byte (0 is opaque), then BGR565 big endian."""
    img = Image.open(png_path).convert("RGBA")
    w, h = img.size
    raw = img.tobytes()
    opaque = all(raw[i] == 255 for i in range(3, len(raw), 4))
    body = bytearray()
    if opaque:
        for i in range(0, len(raw), 4):
            body += struct.pack("<H", bgr565(raw[i], raw[i + 1], raw[i + 2]))
        return b"BM" + struct.pack("<HHHHHHH", 0x08, w, h, w * 2, 16, 0, 0) + bytes(body)
    for i in range(0, len(raw), 4):
        body.append(255 - raw[i + 3])
        body += struct.pack(">H", bgr565(raw[i], raw[i + 1], raw[i + 2]))
    return b"BM" + struct.pack("<HHHHHHH", 0x1B, w, h, w * 3, 24, 0, 0) + bytes(body)


def pack(folder):
    layout = json.load(open(os.path.join(folder, "watchface.json")))
    ids = to_ids(layout, ROOT)
    count = 0
    while os.path.exists(os.path.join(folder, f"{count}.png")):
        count += 1
    images = [encode_image(os.path.join(folder, f"{i}.png")) for i in range(count)]

    sections, info, offset, widest = b"", {1: {1: 0, 2: count}}, 0, 0
    for key in sorted(ids):
        blob = encode(ids[key])
        info[key] = {1: offset, 2: len(blob)}
        sections += blob
        offset += len(blob)
        widest = max(widest, len(blob))
    info[1][1] = len(sections)
    info_bytes = encode(info)

    offsets, body, pos = b"", b"", 0
    for im in images:
        offsets += struct.pack("<I", pos)
        body += im
        pos += len(im)

    # The header's "biggest parameter" is room for the parameter info as well as for every section: the community face
    # has 148 for sections of at most 82 bytes and an info table of 52. A face this small has an info table bigger than
    # its biggest section, so the room is the sum of the two, which is never too little.
    room = max(widest, len(info_bytes) + len(sections))
    head = bytearray(HEADER)
    struct.pack_into("<I", head, len(head) - 8, room)
    struct.pack_into("<I", head, len(head) - 4, len(info_bytes))
    return bytes(head) + info_bytes + sections + offsets + body, ids, images


# ------------------------------------------------------------------ reading it back, to check what was written
def read_varint(buf, pos):
    n, shift = 0, 0
    while True:
        byte = buf[pos]
        pos += 1
        n |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return n, pos
        shift += 7


def decode(buf):
    out, pos = {}, 0
    while pos < len(buf):
        desc, pos = read_varint(buf, pos)
        value, pos = read_varint(buf, pos)
        key = desc >> 3
        if desc & 2:
            child = decode(buf[pos:pos + value])
            pos += value
            value = child
        out[key] = value
    return out


def verify(data, ids, images, folder):
    assert data[:4] == b"UIHH" and data[4] == 1
    size = len(HEADER)
    widest = struct.unpack_from("<I", data, size - 8)[0]
    info_len = struct.unpack_from("<I", data, size - 4)[0]
    info = decode(data[size:size + info_len])
    sections_len, count = info[1][1], info[1][2]
    assert count == len(images)
    base = size + info_len
    for key, expected in ids.items():
        off, ln = info[key][1], info[key][2]
        assert ln <= widest <= info_len + sections_len
        assert decode(data[base + off:base + off + ln]) == expected, f"section {key}"
    table = base + sections_len
    offsets = struct.unpack_from(f"<{count}I", data, table)
    start = table + 4 * count
    for i, off in enumerate(offsets):
        raw = data[start + off:start + off + len(images[i])]
        assert raw == images[i]
        fmt, w, h = struct.unpack_from("<HHH", raw, 2)
        src = Image.open(os.path.join(folder, f"{i}.png")).convert("RGBA").tobytes()
        got = bytearray()
        if fmt == 0x08:
            for j in range(w * h):
                v = struct.unpack_from("<H", raw, 16 + 2 * j)[0]
                got += bytes(((v & 0x001F) << 3, (v & 0x07E0) >> 3, (v & 0xF800) >> 8, 255))
        else:
            assert fmt == 0x1B
            for j in range(w * h):
                alpha = raw[16 + 3 * j]
                v = struct.unpack_from(">H", raw, 17 + 3 * j)[0]
                got += bytes(((v & 0x001F) << 3, (v & 0x07E0) >> 3, (v & 0xF800) >> 8, 255 - alpha))
        want = bytearray()
        for j in range(0, len(src), 4):
            r, g, b2, a2 = src[j:j + 4]
            want += bytes((r & 0xF8, g & 0xFC, b2 & 0xF8, a2))
        assert bytes(got) == bytes(want), f"image {i} pixels"
    assert start + sum(len(im) for im in images) == len(data)
    return size, info_len, sections_len, count


if __name__ == "__main__":
    folder = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, "neon_face")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "NeonPulse.bin")
    data, ids, images = pack(folder)
    open(out, "wb").write(data)
    print("bytes", len(data), "header/info/params/images", verify(data, ids, images, folder))
    print("written", out)
