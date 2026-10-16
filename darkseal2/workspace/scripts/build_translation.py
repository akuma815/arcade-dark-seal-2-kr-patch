"""Dark Seal 2 번역 빌드: 원장(ds2_translation.json) → 부모 ROM 4개(mas02/03 글리프, mas12/13 타일맵) 패치 + FBNeo IPS.

글리프 정책 (2026-10-04 사용자 결정: 단일 스타일)
 - 모든 한글 타일 = 배경 2 + 본체 7 (상자 색/검정은 장면 팔레트가 정함). 프롤로그·NPC(검은 배경)·상자·엔딩 모두 같은 타일을 쓴다.
 - 교체 슬롯 = 글자 뱅크 0xa03~0xb4b + 제2 영역 0xdcf~0xe9b 중, 미번역 레코드가 쓰는 타일과 스태프롤 전용 타일(0xe09~0xe10)을 뺀 것.
 - 원문 문장부호 재사용은 배경 2 스타일 타일만. 숫자·ASCII 부호는 Galmuri11.ttf 11px 렌더.
타일맵
 - msg(상자/프롤로그): span 안을 한글/빈칸(상자 0xa88, 프롤로그 0)으로. line(NPC): 빈칸 0. ending: 빈칸 = 그 행의 비글자 채움 타일.
 - sky: panel_rows 를 전부 0xa88(단색 2 = 검정)로 덮고 가로 줄을 배치, 하단 상자 줄은 ko_box_row. 미러 2벌 동일.
사용: python darkseal2/workspace/scripts/build_translation.py [--name kr] [--no-install] [--min-status draft] [--desc "en|ko"]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ds2lib as L  # noqa: E402
from patchutil import check_allowed, crc32, ips_build  # noqa: E402

LEDGER = L.GAME / "workspace" / "text" / "translation" / "ds2_translation.json"
GMAP = L.GAME / "workspace" / "font" / "mapping" / "ds2_glyph_map.json"
BLOCKS = L.GAME / "workspace" / "text" / "source" / "ds2_blocks.json"
FONT16 = L.ROOT.parent.parent / "Font" / "Galmuri11_16x16.png"
FONT_TTF = L.ROOT.parent.parent / "Font" / "Galmuri11.ttf"
FBNEO_IPS = Path(r"H:\FBNeo v1.0.0.03\support\ips\darkseal2")
STATUS_RANK = {"ignored": -1, "untranslated": 0, "draft": 1, "needs_review": 2, "approved": 3}
# 글리프 스타일: A = 배경 2(상자색/검정 패널 위), B = 배경 0 투명(게임 화면 위에 바로 그리는 대사·엔딩). 2026-10-05 사용자 요청
STYLE_OF_KIND = {"box": "A", "prologue": "A", "sky": "B", "line": "B", "ending": "A"}   # 엔딩은 원본도 배경 2 스타일(채움 타일 위). 하늘 본문은 투명(B), 하단 상자 줄만 A
BOX_BLANK = 0xA88
SKY_BOX_ROW0 = 27
VERTICAL_ONLY = {"「", "」"}                      # 투명 스타일 원본 타일이 세로쓰기 모양인 문장부호(재사용 금지)                              # 하늘 스토리 블록에서 하단 상자(0xa88 채움)가 시작하는 행
CREDITS_TILES = set(range(0xE09, 0xE11))     # 스태프롤 전용(일본어 유지). 0xdc2~0xdce 한자는 스태프롤이 쓰지 않음(credits 레코드 집합으로 확인) → 풀에 포함
PMAP = L.GAME / "workspace" / "font" / "mapping" / "ds2_profile_font_map.json"
FONT8 = L.ROOT.parent.parent / "Font" / "Galmuri7_8x8.png"
PROFILE_BLOCKS = L.GAME / "workspace" / "text" / "source" / "ds2_profile_blocks.json"
# 프로필 폰트에 없는 문장부호는 직접 그린다(8×8 마스크, 본체만 — 그림자는 자동)
HANDMADE8 = {
    ".": [[0] * 8 for _ in range(5)] + [[0, 0, 1, 1, 0, 0, 0, 0], [0, 0, 1, 1, 0, 0, 0, 0], [0] * 8],
    ",": [[0] * 8 for _ in range(4)] + [[0, 0, 1, 1, 0, 0, 0, 0], [0, 0, 1, 1, 0, 0, 0, 0], [0, 0, 0, 1, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0, 0, 0]],
}


def is_hangul(c):
    return 0xAC00 <= ord(c) <= 0xD7A3


def is_font(t):
    return 0xA03 <= t <= 0xB4B or 0xDC2 <= t < 0xE9C


def make_mask(c, sheet, ttf):
    mask = [[0] * 16 for _ in range(16)]
    if is_hangul(c):
        m11 = L.hangul_sheet_glyph(sheet, c, 16)
        for y in range(11):
            for x in range(11):
                mask[y + 2][x + 2] = m11[y][x]
        return mask
    img = Image.new("L", (16, 16), 0)
    ImageDraw.Draw(img).text((2, 1), c, font=ttf, fill=255)
    for y in range(16):
        for x in range(16):
            if img.getpixel((x, y)) > 127:
                mask[y][x] = 1
    if not any(any(r) for r in mask):
        raise SystemExit(f"글리프 렌더 실패 '{c}'")
    return mask


def plain_tile(mask):
    """배경 0(투명) · 본체 7 · 외곽선 2 — 원본 프롤로그/대사 글리프 스타일."""
    return L.mask_to_glyph(mask, body=7, outline=2)


def bg2_tile(mask):
    t = [[2] * 16 for _ in range(16)]
    for y in range(16):
        for x in range(16):
            if mask[y][x]:
                t[y][x] = 7
    return t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="kr")
    ap.add_argument("--no-install", action="store_true")
    ap.add_argument("--min-status", default="draft")
    ap.add_argument("--desc", default="Dark Seal 2 Korean (dev build)|다크씰 2 한글 (개발 빌드)")
    ap.add_argument("--sky-crawl", action="store_true", help="하늘 장면 원본 크롤 유지(정지 코드 패치 생략)")
    a = ap.parse_args()
    min_rank = STATUS_RANK[a.min_status]

    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    gmap = json.loads(GMAP.read_text(encoding="utf-8"))
    blocks = json.loads(BLOCKS.read_text(encoding="utf-8"))
    rec_by_id = {r["id"]: r for r in blocks["records"]}
    if PROFILE_BLOCKS.exists():
        rec_by_id.update({r["id"]: r for r in json.loads(PROFILE_BLOCKS.read_text(encoding="utf-8"))["records"]})

    prg_files, gfx_files = L.load_originals()
    img = L.prg_decode(prg_files)
    assert L.prg_encode(img) == prg_files and img[0x80000:0x100000] == img[0x100000:0x180000]
    enc = L.gfx2_load(gfx_files)
    plain = L.D.deco74_decrypt(enc)
    tiles = L.D.decode_tiles_16x16(plain)
    chk = bytearray(len(plain))
    L.D.encode_tiles_16x16(tiles, chk)
    assert bytes(chk) == plain and L.D.deco74_encrypt(plain) == enc, "왕복 실패"
    print("[OK] 무변경 왕복")

    entries = ledger["entries"]
    translated = [e for e in entries if e["ko_rows"] and STATUS_RANK[e["status"]] >= min_rank]
    untranslated = [e for e in entries if e not in translated and e["status"] != "ignored"]   # ignored = 번역도 보존도 안 함(사용처 없음 판단)

    keep = set(CREDITS_TILES)
    for e in untranslated:
        for row in rec_by_id[e["id"]]["rows"]:
            for h in row:
                w = int(h, 16)
                if w and is_font(w & 0xFFF):
                    keep.add(w & 0xFFF)
    rev_bg2, rev_bg0 = {}, {}
    for k, v in gmap.items():
        t = int(k, 16)
        if v != "▣" and is_font(t):
            if tiles[t][0][0] == 2:
                rev_bg2.setdefault(v, t)
            elif tiles[t][0][0] == 0 and any(any(r) for r in tiles[t]) and v not in VERTICAL_ONLY:
                rev_bg0.setdefault(v, t)      # 세로쓰기용 괄호(하늘 원문)는 가로 글에 못 씀 → 새로 그림
    rev_by_style = {"A": rev_bg2, "B": rev_bg0}

    def style_of(e):
        k = e.get("kind") or ("box" if e["layout"].get("box") else "prologue")
        return STYLE_OF_KIND.get(k, "A")

    need = []
    for e in translated:
        if e.get("kind") in ("profile", "rank", "ascii", "wordrec", "quad"):   # 8×8 경로(아래)에서 따로 처리
            continue
        st = style_of(e)
        texts = [(row, st) for row in e["ko_rows"]]
        if e.get("ko_box_row"):
            texts.append((e["ko_box_row"], "A" if e.get("kind") == "sky" else st))   # 하늘의 상자 줄은 검은 상자 위 → 배경 스타일
        for row, rst in texts:
            for c in row:
                if c != " " and (c, rst) not in need:
                    need.append((c, rst))
    reuse = {(c, st): rev_by_style[st][c] for c, st in need if not is_hangul(c) and c in rev_by_style[st]}
    keep |= set(reuse.values())
    new = [cs for cs in need if cs not in reuse]
    non_glyph = {int(k, 16) for k, v in gmap.items() if v == "▣"} | {BOX_BLANK}      # 상자 채움·틀 조각은 글자가 아니다
    for e in translated:                                                              # 엔딩 채움 타일도 보존
        if e.get("kind") == "ending":
            for row in rec_by_id[e["id"]]["rows"]:
                for h in row:
                    w = int(h, 16)
                    if w and not is_font(w & 0xFFF):
                        non_glyph.add(w & 0xFFF)
    pool = [t for t in sorted(set(int(k, 16) for k in gmap) | set(range(0xA03, 0xB4C))) if is_font(t) and t not in keep and t not in non_glyph]
    if len(new) > len(pool):
        raise SystemExit(f"글리프 슬롯 부족: 필요 {len(new)} > 가용 {len(pool)} (보존 {len(keep)})")
    alloc = {cs: pool[i] for i, cs in enumerate(new)}
    nA = sum(1 for c, st in new if st == "A"); nB = len(new) - nA
    print(f"[OK] 글리프(2스타일 A=배경2 {nA}, B=투명 {nB}): 재사용 {len(reuse)}, 신규 {len(new)} / 가용 {len(pool)}, 보존 {len(keep)}")
    sheet = Image.open(FONT16).convert("RGBA")
    ttf = ImageFont.truetype(str(FONT_TTF), 11)
    for (c, st), t in alloc.items():
        m = make_mask(c, sheet, ttf)
        tiles[t] = bg2_tile(m) if st == "A" else plain_tile(m)

    cur_style = ["A"]

    def tile_for(ch):
        t = reuse.get((ch, cur_style[0])) or alloc.get((ch, cur_style[0]))
        if t is None:
            raise SystemExit(f"타일 없음 '{ch}' (style {cur_style[0]})")
        return t

    new_img = bytearray(img)
    allowed = []
    report = []
    for e in translated:
        if e.get("kind") in ("profile", "rank", "ascii", "wordrec", "quad"):
            continue
        rec = rec_by_id[e["id"]]
        rows = [[int(h, 16) for h in row] for row in rec["rows"]]
        kind = e.get("kind", "box" if e["layout"]["box"] else "prologue")
        cur_style[0] = style_of(e)
        if kind == "sky":
            p0, p1 = e["layout"]["panel_rows"]
            r0 = e["layout"].get("text_row0", p0)
            for r in range(p0, p1 + 1):
                if r0 <= r < SKY_BOX_ROW0:
                    # 투명(원본 세로 텍스트 자리) — 텍스트 행(text_row0~)의 글자 타일 칸만 지운다. 레코드 0행(0xa39d8~)은
                    # 텍스트가 아니라 청크 포인터 표(0x000ae400…: 포인터 하위 워드가 글자 타일 번호처럼 보일 수 있음)라서
                    # 0으로 덮으면 워프 방 배경 포인터가 0이 된다(v1.0.2 결함). 0행은 건드리지 않는다.
                    rows[r] = [0 if (w and is_font(w & 0xFFF)) else w for w in rows[r]]
                # 상자 영역(행 27~)은 원본 그대로 두고 아래에서 상자 줄만 다시 쓴다
            if r0 + len(e["ko_rows"]) - 1 > p1:
                raise SystemExit(f"{e['id']}: 줄 {len(e['ko_rows'])} > 패널 행 {r0}~{p1}")
            for i, text in enumerate(e["ko_rows"]):
                for k, ch in enumerate(text):
                    if ch != " ":
                        rows[r0 + i][k] = tile_for(ch)
            # 하단 상자 줄: span 이 있는 패널 밖 행
            # (2026-10-05) panel_rows 가 상자 행까지 덮도록 바뀐 뒤 "패널 밖" 조건이 빈 집합이 되어 상자 줄이 원문 타일 그대로 남았다
            #  → 요새 접근 컷신 첫 대사(같은 행 0xa3e38 을 공유)가 의미불명 한글로 표시됨(EKMAME 제보). 행 번호 기준으로 고정.
            box_rows = [i for i, lay in enumerate(e["layout"]["rows"]) if lay["span"] and i >= SKY_BOX_ROW0]
            if e.get("ko_box_row") and not box_rows:
                raise SystemExit(f"{e['id']}: 상자 줄(행 ≥{SKY_BOX_ROW0}) 을 찾지 못함")
            if e.get("ko_box_row") and box_rows:
                i = box_rows[-1]
                c0, c1 = e["layout"]["rows"][i]["span"]
                fill = Counter(w & 0xFFF for w in rows[i][c0:c1 + 1] if w and not is_font(w & 0xFFF)).most_common(1)
                blank = fill[0][0] if fill else BOX_BLANK
                for k in range(c0, c1 + 1):
                    rows[i][k] = blank
                text = e["ko_box_row"]
                if len(text) > c1 - c0 + 1:
                    raise SystemExit(f"{e['id']} 상자 줄 {len(text)}셀 > {c1 - c0 + 1}")
                cur_style[0] = "A"                           # 상자 줄은 검은 상자 위 → 배경 2 스타일
                for k, ch in enumerate(text):
                    if ch != " ":
                        rows[i][c0 + k] = tile_for(ch)
                cur_style[0] = style_of(e)
        else:
            for i, lay in enumerate(e["layout"]["rows"]):
                span = lay["span"]
                if span is None:
                    continue
                text = e["ko_rows"][i] if i < len(e["ko_rows"]) else ""
                c0, c1 = span
                if len(text) > c1 - c0 + 1:
                    raise SystemExit(f"{e['id']} 행{i}: {len(text)}셀 > span {c1 - c0 + 1}")
                if kind == "box":
                    blank = BOX_BLANK
                elif kind == "ending":
                    fill = Counter(w & 0xFFF for w in rows[i][c0:c1 + 1] if w and not is_font(w & 0xFFF)).most_common(1)
                    blank = fill[0][0] if fill else 0
                else:
                    blank = 0
                for k in range(c0, c1 + 1):
                    rows[i][k] = blank
                for k, ch in enumerate(text):
                    if ch != " ":
                        rows[i][c0 + k] = tile_for(ch)
        base = int(rec["addr"], 16)
        data = b"".join(w.to_bytes(2, "big") for row in rows for w in row)
        for mirror in (0, L.MIRROR):
            new_img[base + mirror:base + mirror + len(data)] = data
            allowed.append((base + mirror, base + mirror + len(data)))
        report.append({"id": e["id"], "label": e.get("label", ""), "rows": len(e["ko_rows"])})
    # ---- 프로필 화면(8×8 타일맵 블록 + 문자 ROM jb-04/05) ----
    profiles = [e for e in translated if e.get("kind") == "profile"]
    rank_entries = [e for e in translated if e.get("kind") == "rank"]
    ascii_entries = [e for e in translated if e.get("kind") == "ascii"]
    wordrec_entries = [e for e in translated if e.get("kind") == "wordrec"]
    quad_entries = [e for e in translated if e.get("kind") == "quad"]
    gfx0_changed = {}
    prof_alloc = {}
    if profiles or rank_entries or ascii_entries or wordrec_entries or quad_entries:
        pmap = json.loads(PMAP.read_text(encoding="utf-8"))
        rev_pf = {}
        for k, v in pmap.items():
            if v != "▣" and len(v) == 1:
                rev_pf.setdefault(v, int(k, 16))
        rev_pf["·"] = rev_pf.get("・", rev_pf.get("·"))
        rev_pf["“"] = rev_pf.get("〝"); rev_pf["”"] = rev_pf.get("〞")
        gfx0 = L.D.deco74_decrypt(L.D.interleave(gfx_files[L.GFX0_FILES[0]], gfx_files[L.GFX0_FILES[1]]))
        tiles8 = L.D.decode_tiles_8x8(gfx0)
        need8 = []
        for e in wordrec_entries:
            for text in e["ko_rows"]:
                for c in text:
                    if c != " " and c not in need8 and c not in rev_pf:
                        need8.append(c)
        for e in profiles:
            for segs in e["ko_cells"].values():
                for _, text in segs:
                    for c in text:
                        if c != " " and c not in need8 and c not in rev_pf:
                            need8.append(c)
        for e in rank_entries:
            for text in e["ko_rows"]:
                for c in text:
                    if c != " " and c not in need8 and c not in rev_pf:
                        need8.append(c)
        free = list(range(L.PROFILE_FREE_TILES[1] - 1, L.PROFILE_FREE_TILES[0] - 1, -1))   # 0xbff 부터 내려가며
        bad = [c for c in need8 if not (is_hangul(c) or c in HANDMADE8)]
        if bad:
            raise SystemExit(f"프로필: 공급 불가 문자 {bad}")
        if len(need8) > len(free):
            raise SystemExit(f"프로필 8×8 슬롯 부족: {len(need8)} > {len(free)}")
        sheet8 = Image.open(FONT8).convert("RGBA")
        for i, c in enumerate(need8):
            t = free[i]
            if not any(any(r) for r in tiles8[t]):
                pass
            else:
                raise SystemExit(f"프로필: 빈 타일이 아님 {t:03x}")
            mask = HANDMADE8[c] if c in HANDMADE8 else L.hangul_sheet_glyph(sheet8, c, 8)
            tiles8[t] = L.hangul8_tile(mask)
            prof_alloc[c] = t
        print(f"[OK] 프로필 8×8 글리프: 재사용 {sum(1 for e in profiles for s in e['ko_cells'].values() for _, tx in s for c in tx if c != ' ' and c in rev_pf)}셀, 신규 {len(need8)} / 가용 {len(free)}")

        def tile8_for(ch):
            t = prof_alloc.get(ch)
            if t is None:
                t = rev_pf.get(ch)
            if t is None:
                raise SystemExit(f"프로필 타일 없음 '{ch}'")
            return t

        marks = {0xF03, 0xF2E, 0xEDD, 0xF00}
        for e in profiles:
            rec = rec_by_id[e["id"]]
            rows = [[int(h, 16) for h in row] for row in rec["rows"]]
            lay = e["layout"]
            glyph_words = [w for row in rows for w in row if w and L.PROFILE_FONT[0] <= (w & 0xFFF) < L.PROFILE_FONT[1] and (w & 0xFFF) not in marks]
            pal_default = Counter(w >> 12 for w in glyph_words).most_common(1)[0][0]
            def is_glyph(w):
                return bool(w) and L.PROFILE_FONT[0] <= (w & 0xFFF) < L.PROFILE_FONT[1]
            def blank_of(r, c0, c1):
                cand = [w for w in rows[r][c0:c1 + 1] if not is_glyph(w)]
                return Counter(cand).most_common(1)[0][0] if cand else 0
            # 1) 탁점 행 정리: 글자 행 위의 탁점 타일을 지운다 (행 1 의 edd 는 틀 조각 eba 로)
            for r in range(32):
                for c in range(40):
                    t = rows[r][c] & 0xFFF
                    if rows[r][c] and t in marks:
                        pal = rows[r][c] >> 12
                        rows[r][c] = (pal << 12) | 0xEBA if t == 0xEDD else blank_of(r, 1, 38)
            # 2) 스탯 행·본문 행: 지정 영역을 비우고 한글 기록
            spans = {int(k): v for k, v in lay["stat_rows"].items()}
            b0, b1 = lay["body_rows"]; bc0, bc1 = lay["body_cols"]
            for r in range(b0, b1 + 1):
                spans.setdefault(r, [bc0, bc1])
            spans[16] = [1, 38]                 # 'プロフィール' 제목 행(P9~11 은 이름 2행째도 여기)
            for r, span in spans.items():
                c0, c1 = span
                pal_row = Counter(w >> 12 for w in rows[r][c0:c1 + 1] if is_glyph(w)).most_common(1)
                pal = pal_row[0][0] if pal_row else pal_default
                blank = blank_of(r, c0, c1)
                for c in range(c0, c1 + 1):
                    rows[r][c] = blank
                for col, text in e["ko_cells"].get(str(r), []):
                    if col < c0 or col + len(text) - 1 > c1:
                        raise SystemExit(f"{e['id']} 행{r}: 열{col}+{len(text)} 가 영역 {span} 밖")
                    for k, ch in enumerate(text):
                        if ch != " ":
                            rows[r][col + k] = (pal << 12) | tile8_for(ch)
            base = int(rec["addr"], 16)
            data = b"".join(w.to_bytes(2, "big") for row in rows for w in row)
            for mirror in (0, L.MIRROR):
                new_img[base + mirror:base + mirror + len(data)] = data
                allowed.append((base + mirror, base + mirror + len(data)))
            report.append({"id": e["id"], "label": e.get("label", ""), "rows": len(e["ko_rows"])})
        # ASCII 레코드(랭킹 제목·직업 라벨): 글리프는 0x929~0x9fe 에 따로 배정
        if ascii_entries:
            need_a = []
            for e in ascii_entries:
                for text in e["ko_rows"]:
                    for c in text:
                        if c != " " and c not in need_a:
                            need_a.append(c)
            a0, a1 = L.ASCII_GLYPH_RANGE
            if len(need_a) > a1 - a0 + 1:
                raise SystemExit(f"ASCII 레코드 글리프 초과 {len(need_a)}")
            ascii_alloc = {}
            for i, c in enumerate(need_a):
                t = a0 + i
                if any(any(r) for r in tiles8[t]):
                    raise SystemExit(f"ASCII 글리프 자리 {t:03x} 가 비어 있지 않음")
                mask = HANDMADE8[c] if c in HANDMADE8 else L.hangul_sheet_glyph(sheet8, c, 8)
                tiles8[t] = L.hangul8_tile(mask)
                ascii_alloc[c] = t
                prof_alloc[f"ascii:{c}"] = t
            cur = L.ASCII_NEW_RECORDS
            for e in ascii_entries:
                idx = int(e["addr"], 16)
                segs = e["layout"]["segments"]
                if len(e["ko_rows"]) != len(segs):
                    raise SystemExit(f"{e['id']}: 세그먼트 {len(segs)} != 한글 {len(e['ko_rows'])}")
                rec = bytearray()
                for sg, text in zip(segs, e["ko_rows"]):
                    center = sg["col"] + sg["len"] / 2
                    col = max(0, round(center - len(text) / 2))
                    dest = 0x200000 + sg["row"] * 128 + col * 2
                    attr = (sg["attr"] & 0xF000) | L.ASCII_ATTR          # 원본 팔레트 유지 + 타일 상위 0x900
                    rec += attr.to_bytes(2, "big") + dest.to_bytes(4, "big")
                    for ch in text:
                        t = L.ASCII_SPACE_TILE if ch == " " else ascii_alloc[ch]
                        rec.append(t - (L.ASCII_ATTR & 0xF00))
                    if len(text) % 2:
                        rec.append(0x00)             # 원본("ELF+0")처럼 홀수 길이는 0 패딩 → 다음 세그먼트 attr/dest 가 짝수 주소(68000 어드레스 에러 방지)
                    rec += bytes([0xFF, 0xFE])
                rec[-2:] = bytes([0xFF, 0xFF])
                if any(b != 0xFF for b in img[cur:cur + len(rec)]):
                    raise SystemExit(f"ASCII 레코드 자리 {cur:05x} 가 비어 있지 않음")
                new_img[cur:cur + len(rec)] = rec
                new_img[L.ASCII_TABLE + 4 * idx:L.ASCII_TABLE + 4 * idx + 4] = cur.to_bytes(4, "big")
                allowed += [(cur, cur + len(rec)), (L.ASCII_TABLE + 4 * idx, L.ASCII_TABLE + 4 * idx + 4)]
                report.append({"id": e["id"], "label": e.get("label", ""), "rows": len(e["ko_rows"])})
                cur += len(rec)
                if cur % 2:                      # 68000: 다음 레코드 시작은 짝수 주소여야 함(MAME 계열은 홀수 워드 접근 → 어드레스 에러). FBNeo 는 묵인해 2026-10-05 EKMAME 제보로 발견
                    cur += 1
            for idx in (int(e["addr"], 16) for e in ascii_entries):
                ptr = int.from_bytes(new_img[L.ASCII_TABLE + 4 * idx:L.ASCII_TABLE + 4 * idx + 4], "big")
                if ptr % 2:
                    raise SystemExit(f"ASCII 레코드 {idx:02x} 포인터가 홀수 주소 {ptr:05x}")
                for attr, dest, _ in L.ascii_record_segments(bytes(new_img), idx):
                    if dest % 2:
                        raise SystemExit(f"ASCII 레코드 {idx:02x} dest 홀수 {dest:06x}")
                o = ptr
                while True:                      # 세그먼트 시작(attr 워드) 주소가 모두 짝수인지
                    if o % 2:
                        raise SystemExit(f"ASCII 레코드 {idx:02x} 세그먼트가 홀수 주소 {o:05x}")
                    o += 6
                    while not (new_img[o] == 0xFF and new_img[o + 1] in (0xFE, 0xFF)):
                        o += 1
                    if new_img[o + 1] == 0xFF:
                        break
                    o += 2
            print(f"[OK] ASCII 레코드 {len(ascii_entries)}개 한글화: 글리프 {len(need_a)} @0x929~, 레코드 @{L.ASCII_NEW_RECORDS:05x}~{cur:05x} (짝수 정렬 확인)")
        for e in wordrec_entries:
            start = int(e["addr"], 16); end = int(e["layout"]["end"], 16)
            text_segs = [sg for sg in e["layout"]["segments"] if not sg["mark"]]
            if len(e["ko_rows"]) != len(text_segs):
                raise SystemExit(f"{e['id']}: 세그먼트 {len(text_segs)} != 한글 {len(e['ko_rows'])}")
            rec = bytearray()
            for sg, text in zip(text_segs, e["ko_rows"]):
                if len(text) > 38 - sg["col"]:
                    raise SystemExit(f"{e['id']}: '{text}' 가 화면을 넘음(열 {sg['col']})")
                rec += sg["dest"].to_bytes(4, "big")
                for ch in text:
                    rec += ((sg["pal"] << 12) | (0x20 if ch == " " else tile8_for(ch))).to_bytes(2, "big")
                rec += bytes([0xFF, 0xFE])
            rec[-2:] = bytes([0xFF, 0xFF])
            if len(rec) > end - start:
                raise SystemExit(f"{e['id']}: 레코드 {len(rec)}B > 자리 {end - start}B")
            rec += bytes([0xFF]) * (end - start - len(rec))
            new_img[start:end] = rec
            allowed.append((start, end))
            report.append({"id": e["id"], "label": e.get("label", ""), "rows": len(e["ko_rows"])})
            print(f"[OK] 워드 레코드 {e['id']}: {len(rec)}B 제자리 재기록")
        # ---- 쿼드 대사(QD:*): 16×16 한글을 8×8 네 장으로 쪼개 빈 타일에 배정, 레코드 제자리 재기록
        if quad_entries:
            needq = []
            for e in quad_entries:
                for text in e["ko_rows"]:
                    for c in text:
                        if c != " " and c not in needq and c not in L.QUAD_REUSE:
                            needq.append(c)
            used_now = set(prof_alloc.values())
            freeq = [t for t in range(L.PROFILE_FREE_TILES[0], L.PROFILE_FREE_TILES[1]) if t not in used_now and not any(any(r) for r in tiles8[t])]
            groups = []
            i = 0
            while i + 3 < len(freeq):
                if freeq[i + 3] == freeq[i] + 3:
                    groups.append(freeq[i])
                    i += 4
                else:
                    i += 1
            if len(needq) > len(groups):
                raise SystemExit(f"쿼드 글리프 슬롯 부족: 필요 {len(needq)} > 가용 {len(groups)}")
            qalloc = {}
            for c, k in zip(needq, groups):
                mask = make_mask(c, sheet, ttf)
                t16 = L.mask_to_glyph(mask, body=7, outline=2)      # 원본 쿼드 가나와 동일: 본체 7(흰색), 외곽선 2 (영숫자 쿼드는 1/2)
                for q, sub in enumerate(L.quad_split(t16)):
                    tiles8[k + q] = sub
                    prof_alloc[f"quad:{c}:{q}"] = k + q
                qalloc[c] = k
            for e in quad_entries:
                idx = [k for k, v in L.QUAD_RECORDS.items() if v == e["id"]][0]
                start, end, segs = L.quad_record(img, idx)
                if len(e["ko_rows"]) > len(segs):
                    raise SystemExit(f"{e['id']}: 줄 {len(e['ko_rows'])} > 세그먼트 {len(segs)}")
                rec = bytearray()
                texts = list(e["ko_rows"]) + [""] * (len(segs) - len(e["ko_rows"]))
                for (attr, dest, ws), text in zip(segs, texts):
                    if len(text) > 20:
                        raise SystemExit(f"{e['id']}: '{text}' {len(text)}글자 > 20")
                    rec += attr.to_bytes(2, "big") + dest.to_bytes(4, "big")
                    text = text + " " * max(0, len(ws) - len(text))       # 원본 길이만큼 공백으로 채워 이전 대사를 지운다
                    for ch in text:
                        k = 0 if ch == " " else (L.QUAD_REUSE.get(ch) or qalloc[ch])
                        rec += k.to_bytes(2, "big")
                    rec += bytes([0xFF, 0xFE])
                rec[-2:] = bytes([0xFF, 0xFF])
                if len(rec) > end - start:
                    raise SystemExit(f"{e['id']}: 레코드 {len(rec)}B > 자리 {end - start}B")
                rec += bytes([0xFF]) * (end - start - len(rec))
                new_img[start:end] = rec
                allowed.append((start, end))
                report.append({"id": e["id"], "label": e.get("label", ""), "rows": len(e["ko_rows"])})
            print(f"[OK] 쿼드 대사 {len(quad_entries)}개: 글리프 {len(needq)} (가용 {len(groups)}), 제자리 재기록")
        for e in rank_entries:
            if len(e["ko_rows"]) != L.RANK_COUNT:
                raise SystemExit(f"{e['id']}: 계급명 {len(e['ko_rows'])}개 != {L.RANK_COUNT}")
            addr, orig, new = L.RANK_COPY_PATCH
            if img[addr:addr + len(orig)] != orig:
                raise SystemExit(f"계급 복사 루프 원본 불일치 @{addr:05x}")
            new_img[addr:addr + len(new)] = new
            allowed.append((addr, addr + len(new)))
            for i, name in enumerate(e["ko_rows"]):
                if len(name) > L.RANK_CELLS:
                    raise SystemExit(f"{e['id']}: '{name}' {len(name)}셀 > {L.RANK_CELLS}")
                words = [tile8_for(ch) if ch != " " else L.RANK_BLANK for ch in name] + [L.RANK_BLANK] * (L.RANK_CELLS - len(name))
                dst = L.RANK_NEW_STRINGS + i * L.RANK_CELLS * 2
                if any(b != 0xFF for b in img[dst:dst + L.RANK_CELLS * 2]):
                    raise SystemExit(f"계급 문자열 자리 {dst:05x} 가 비어 있지 않음")
                new_img[dst:dst + L.RANK_CELLS * 2] = b"".join(w.to_bytes(2, "big") for w in words)
                new_img[L.RANK_TABLE + 4 * i:L.RANK_TABLE + 4 * i + 4] = dst.to_bytes(4, "big")
                allowed += [(dst, dst + L.RANK_CELLS * 2), (L.RANK_TABLE + 4 * i, L.RANK_TABLE + 4 * i + 4)]
            report.append({"id": e["id"], "label": e.get("label", ""), "rows": len(e["ko_rows"])})
            print(f"[OK] 계급명 {L.RANK_COUNT}개 → 워드 문자열 @{L.RANK_NEW_STRINGS:05x}, 복사 루프 패치")
        if any(e["id"] == "PF:4" for e in profiles):
            addr, orig, new = L.PROFILE_OVERLAY_PATCH
            if img[addr:addr + len(orig)] != orig:
                raise SystemExit(f"프로필 오버레이 원본 불일치 @{addr:05x}: {img[addr:addr + len(orig)].hex()}")
            new_img[addr:addr + len(new)] = new
            allowed.append((addr, addr + len(new)))
            print("[OK] 프로필 P4 'Morning Star' 오버레이 무효화 (0x7ca6)")
        new_gfx0 = bytearray(len(gfx0))
        L.D.encode_tiles_8x8(tiles8, new_gfx0)
        half8 = len(gfx0) // 2
        allowed8 = []
        for t in prof_alloc.values():
            allowed8 += [(t * 16, t * 16 + 16), (half8 + t * 16, half8 + t * 16 + 16)]
        check_allowed(gfx0, bytes(new_gfx0), allowed8, "gfx0")
        ev, od = L.D.deinterleave(L.D.deco74_encrypt(bytes(new_gfx0)))
        gfx0_changed = {L.GFX0_FILES[0]: ev, L.GFX0_FILES[1]: od}

    code_patches = []
    if any(e.get("kind") == "sky" for e in translated) and not a.sky_crawl:
        for addr, orig, new in L.SKY_SCENE_PATCHES:
            if img[addr:addr + len(orig)] != orig:
                raise SystemExit(f"코드 패치 원본 불일치 @{addr:05x}: {img[addr:addr + len(orig)].hex()}")
            new_img[addr:addr + len(new)] = new
            allowed.append((addr, addr + len(new)))
            code_patches.append({"addr": f"{addr:05x}", "orig": orig.hex(), "new": new.hex()})
        print(f"[OK] 하늘 장면 정지 패치 {len(code_patches)}곳 (X=0 고정, 유지 0x200 프레임)")
    check_allowed(img, bytes(new_img), allowed, "prg")

    new_plain = bytearray(len(plain))
    L.D.encode_tiles_16x16(tiles, new_plain)
    half = len(plain) // 2
    allowed_g = []
    for t in alloc.values():
        allowed_g += [(t * 64, t * 64 + 64), (half + t * 64, half + t * 64 + 64)]
    check_allowed(plain, bytes(new_plain), allowed_g, "gfx2")
    new_enc = L.D.deco74_encrypt(bytes(new_plain))
    print(f"[OK] Expected Write: 레코드 {len(report)}, 타일 {len(alloc)}")

    build = L.GAME / "build" / a.name
    build.mkdir(parents=True, exist_ok=True)
    orig_all = {**prg_files, **gfx_files}
    new_all = {**L.prg_encode(bytes(new_img)), **L.gfx2_split(new_enc), **gfx0_changed}
    dat_lines, roms = [], {}
    for name, data in new_all.items():
        fname = name.split("/")[-1]
        (build / fname).write_bytes(data)
        if data != orig_all[name]:
            ips_name = f"{a.name}-{fname.replace('.', '_')}"
            (build / f"{ips_name}.ips").write_bytes(ips_build(orig_all[name], data))
            dat_lines.append(f"{fname}\t{ips_name}\tCRC({crc32(orig_all[name])})")
            roms[fname] = {"changed_bytes": sum(1 for x, y in zip(orig_all[name], data) if x != y), "ips": ips_name + ".ips", "crc": crc32(orig_all[name])}
    desc_en, _, desc_ko = a.desc.partition("|")
    (build / f"{a.name}.dat").write_text("\n".join(dat_lines) + f"\n\n[en_US]\n{desc_en}\n\n[ko_KR]\n{desc_ko or desc_en}\n", encoding="utf-8")
    (build / "report.json").write_text(json.dumps({"scripts": report, "code_patches": code_patches, "roms": roms, "glyph_alloc": {f"{c}:{st}": f"{t:03x}" for (c, st), t in alloc.items()},
                                                   "profile_glyph_alloc": {c: f"{t:03x}" for c, t in prof_alloc.items()},
                                                   "untranslated": [e["id"] for e in untranslated]}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[OK] build:", ", ".join(f"{k} ({v['changed_bytes']}B)" for k, v in roms.items()))
    if not a.no_install:
        FBNEO_IPS.mkdir(parents=True, exist_ok=True)
        for f in [build / f"{a.name}.dat"] + list(build.glob(f"{a.name}-*.ips")):
            shutil.copy(f, FBNEO_IPS / f.name)
        print(f"[OK] FBNeo support/ips/darkseal2/{a.name}.dat 설치")
    return 0


if __name__ == "__main__":
    sys.exit(main())
