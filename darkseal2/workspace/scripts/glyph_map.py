"""2편 글리프(16×16 타일)↔문자 전사표 도구. 표: workspace/font/mapping/ds2_glyph_map.json { "a59": "ガ", … }

- sheet : 텍스트 뱅크(0x9c0~0xb3f) 중 미전사 타일을 라벨 시트로 (work/glyph_sheets2/, order.txt)
- fill  : 행 단위 전사 JSON({'S01 r1': '…'}) 을 order.txt 와 zip 해 표에 추가
- decode: 메시지 레코드를 문자열로 복원 → text/source/ds2_text_ja.json (미전사 〔xxx〕, 빈 셀 전각 공백)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ds2lib as L  # noqa: E402

sys.path.insert(0, str(L.ROOT / "common" / "scripts"))
from render_chars import PALETTE  # noqa: E402

SRC = L.GAME / "workspace" / "text" / "source"
MAP = L.GAME / "workspace" / "font" / "mapping" / "ds2_glyph_map.json"
SHEETS = L.GAME / "work" / "glyph_sheets2"
TEXT_BANK = (0x9C0, 0xB60)   # 메시지 글자 타일 범위 (0xb40~0xb4b 도 후반 대사에서 사용)


def load_map():
    return json.loads(MAP.read_text(encoding="utf-8")) if MAP.exists() else {}


def save_map(m):
    MAP.parent.mkdir(parents=True, exist_ok=True)
    MAP.write_text(json.dumps(dict(sorted(m.items())), ensure_ascii=False, indent=1), encoding="utf-8")


def tiles16():
    _, gfx = L.load_originals()
    plain = L.D.deco74_decrypt(L.gfx2_load(gfx))
    return L.D.decode_tiles_16x16(plain)


def cmd_sheet(a):
    blocks = json.loads((SRC / "ds2_blocks.json").read_text(encoding="utf-8"))
    m = load_map()
    used = sorted(int(k, 16) for k in blocks["tile_usage"] if TEXT_BANK[0] <= int(k, 16) < TEXT_BANK[1])
    todo = [t for t in used if f"{t:03x}" not in m] if not a.all else used
    tiles = tiles16()
    S, cols, rows_per = a.scale, a.cols, a.rows
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = None
    cell_w, cell_h = 16 * S + 12, 16 * S + 26
    per = cols * rows_per
    SHEETS.mkdir(parents=True, exist_ok=True)
    for f in SHEETS.glob("*.png"):
        f.unlink()
    order = []
    for si in range(0, len(todo), per):
        chunk = todo[si:si + per]
        nrows = (len(chunk) + cols - 1) // cols
        img = Image.new("RGB", (cols * cell_w + 40, nrows * cell_h), (24, 24, 24))
        dr = ImageDraw.Draw(img)
        for i, t in enumerate(chunk):
            px = tiles[t]
            ox, oy = 40 + (i % cols) * cell_w + 6, (i // cols) * cell_h + 2
            for y in range(16):
                for x in range(16):
                    v = px[y][x]
                    if v:
                        col = (255, 255, 255) if v == 7 else (255, 90, 90) if v == 2 else (120, 200, 255)
                        dr.rectangle((ox + x * S, oy + y * S, ox + x * S + S - 1, oy + y * S + S - 1), fill=col)
            dr.text((ox, oy + 16 * S + 2), f"{t:03x}", fill=(255, 255, 0), font=font)
        for r in range(nrows):
            dr.text((2, r * cell_h + 16 * S // 2), f"r{r + 1}", fill=(0, 255, 255), font=font)
        sheet_no = si // per + 1
        img.save(SHEETS / f"glyphs_{sheet_no:02d}.png")
        for r in range(nrows):
            order.append(f"S{sheet_no:02d} r{r + 1}: " + " ".join(f"{t:03x}" for t in chunk[r * cols:(r + 1) * cols]))
    (SHEETS / "order.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    print("\n".join(order))
    print(f"[OK] todo={len(todo)} of used={len(used)} → {SHEETS}")


def cmd_fill(a):
    order = {}
    for line in (SHEETS / "order.txt").read_text(encoding="utf-8").splitlines():
        k, codes = line.split(":", 1)
        order[k.strip()] = [int(c, 16) for c in codes.split()]
    rows = json.loads(Path(a.json_path).read_text(encoding="utf-8"))
    m = load_map()
    n = 0
    for key, text in rows.items():
        if key.startswith("_"):
            continue
        codes = order.get(key)
        chars = [c for c in text if c not in " \n"]
        if codes is None or len(chars) != len(codes):
            print(f"  [mismatch] {key}: codes={len(codes) if codes else None} chars={len(chars)} → 건너뜀: {text}")
            continue
        for t, c in zip(codes, chars):
            k = f"{t:03x}"
            if k in m and m[k] != c:
                print(f"  conflict {k}: '{m[k]}' vs '{c}'")
            m[k] = c
            n += 1
    save_map(m)
    print(f"[OK] filled {n}, map entries={len(m)}")


def cmd_decode(a):
    blocks = json.loads((SRC / "ds2_blocks.json").read_text(encoding="utf-8"))
    m = load_map()
    out = {}
    missing = set()
    for rec in blocks["records"]:
        lines = []
        for row in rec["rows"]:
            s = ""
            for h in row:
                w = int(h, 16)
                t = w & 0xFFF
                if not w:
                    s += "　"
                elif TEXT_BANK[0] <= t < TEXT_BANK[1]:
                    if f"{t:03x}" in m:
                        s += m[f"{t:03x}"]
                    else:
                        s += f"〔{t:03x}〕"
                        missing.add(t)
                else:
                    s += "▣"
            lines.append(s.rstrip("　"))
        out[rec["id"]] = {"row0": rec["row0"], "lines": lines}
    p = SRC / "ds2_text_ja.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] {p.name}: records={len(out)} unmapped={len(missing)}")
    for sid, rec in out.items():
        print(f"== {sid} (row {rec['row0']})")
        for l in rec["lines"]:
            if l.strip("　"):
                print("   ", l)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sheet")
    s.add_argument("--all", action="store_true")
    s.add_argument("--cols", type=int, default=8)
    s.add_argument("--rows", type=int, default=6)
    s.add_argument("--scale", type=int, default=4)
    f = sub.add_parser("fill")
    f.add_argument("json_path")
    sub.add_parser("decode")
    a = ap.parse_args()
    {"sheet": cmd_sheet, "fill": cmd_fill, "decode": cmd_decode}[a.cmd](a)


if __name__ == "__main__":
    main()
