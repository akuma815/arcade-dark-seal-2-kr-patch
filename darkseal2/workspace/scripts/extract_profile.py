"""프로필 화면(8×8 타일맵 블록 P4~P11) 추출 → text/source/ds2_profile_blocks.json, 원장(ds2_translation.json)에 kind=profile 항목 추가.

블록 = 40×32 워드. 글자 타일(0xeb8~0xf79)을 font/mapping/ds2_profile_font_map.json 으로 복원하고, 홀수 행의 탁점 타일(f03/f2e=゛, f00=゜, edd=틀+゛)은
아래 행 글자에 합친다. 한글 레이아웃: 스탯 행은 원문 라벨 열부터 열 38 까지, 본문은 행 17~28 × 열 1~38 (원문은 짝수 행만 사용, 홀수 행은 탁점).
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ds2lib as L  # noqa: E402

SRC = L.GAME / "workspace" / "text" / "source" / "ds2_profile_blocks.json"
LEDGER = L.GAME / "workspace" / "text" / "translation" / "ds2_translation.json"
MAP = L.GAME / "workspace" / "font" / "mapping" / "ds2_profile_font_map.json"
DAKU = dict(zip("かきくけこさしすせそたちつてとはひふへほカキクケコサシスセソタチツテトハヒフヘホウ",
                "がぎぐげござじずぜぞだぢづでどばびぶべぼガギグゲゴザジズゼゾダヂヅデドバビブベボヴ"))
HAN = dict(zip("はひふへほハヒフヘホ", "ぱぴぷぺぽパピプペポ"))
MARK_DAKU = {0xF03, 0xF2E, 0xEDD}
MARK_HAN = {0xF00}
# 라벨 행(스탯 5인): (행, 글자 시작 열) — 값은 라벨 뒤. 본문: 행 17~28.
STAT_ROWS = {2: "NAME", 4: "CLASS", 5: "CLASS2", 6: "ALIGNMENT", 8: "SEX/AGE", 10: "HEIGHT/WEIGHT", 12: "HAIR/EYES", 13: "HAIR/EYES2", 14: "WEAPON"}


def decode_block(words: list[int], m: dict[str, str]) -> list[str]:
    rows = [words[r * 40:(r + 1) * 40] for r in range(32)]
    out = []
    for r in range(32):
        line = []
        for c in range(40):
            t = rows[r][c] & 0xFFF
            if not rows[r][c] or t < L.PROFILE_FONT[0] or t >= L.PROFILE_FONT[1] or t in MARK_DAKU or t in MARK_HAN:
                line.append(" ")
                continue
            ch = m.get(f"{t:03x}", "▣")      # 표에 없는 타일 = 틀 조각
            if ch == "▣":
                line.append(" ")
                continue
            above = (rows[r - 1][c] & 0xFFF) if r and rows[r - 1][c] else 0
            if above in MARK_DAKU:
                ch = DAKU.get(ch, ch + "゛")
            elif above in MARK_HAN:
                ch = HAN.get(ch, ch + "゜")
            line.append(ch)
        out.append("".join(line).rstrip())
    return out


def main() -> int:
    m = json.loads(MAP.read_text(encoding="utf-8"))
    prg_files, _ = L.load_originals()
    img = L.prg_decode(prg_files)
    addrs = L.profile_block_addrs(img)
    records = []
    for idx in range(4, 12):
        a = addrs[idx]
        words = list(struct.unpack(f">{40 * 32}H", img[a:a + 2560]))
        text = decode_block(words, m)
        full = idx <= 8
        rec = {
            "id": f"PF:{idx}", "kind": "profile", "addr": f"{a:06x}", "block_index": idx, "full_stats": full,
            "rows": [[f"{w:04x}" for w in words[r * 40:(r + 1) * 40]] for r in range(32)],
            "source_text": {str(r): text[r] for r in range(32) if text[r].strip()},
            "layout": {
                # 한글이 쓸 수 있는 영역: (행, 시작열, 끝열). 스탯 행은 라벨 포함 교체, 본문은 행 17~28 열 1~38
                "stat_rows": ({2: [15, 38], 4: [15, 38], 5: [15, 38], 6: [15, 38], 8: [15, 38], 10: [15, 38], 12: [15, 38], 13: [14, 38], 14: [14, 38]}
                              if full else {15: [12, 38], 16: [12, 38]}),
                "body_rows": [17, 28], "body_cols": [1, 38],
                "title_row": 16 if not full else None,       # P9~11: 행 16 열 1~6 'プロフィール' 라벨
            },
        }
        records.append(rec)
    ranks = [img[0x2534 + 6 * i:0x2534 + 6 * i + 6].decode("ascii").strip() for i in range(L.RANK_COUNT)]
    records.append({"id": "RK:0", "kind": "rank", "addr": "002534", "rows": [], "source_text": {str(i): r for i, r in enumerate(ranks)},
                    "layout": {"cells": L.RANK_CELLS, "note": "계급명 6개, 각 ≤6셀(8×8), 왼쪽 정렬. 루틴 0x2410 → pf0"}})
    kana8 = json.loads((L.GAME / "workspace" / "font" / "mapping" / "ds2_kana8_map.json").read_text(encoding="utf-8"))
    for start, (rid, end) in L.WORDREC_RECORDS.items():
        segs = L.wordrec_segments(img, start)
        texts, layout = {}, []
        for i, (dest, ws) in enumerate(segs):
            off = dest - 0x200000
            is_mark = all((w & 0xFFF) == L.WORDREC_MARK for w in ws)
            layout.append({"dest": dest, "row": off // 128, "col": (off % 128) // 2, "len": len(ws), "mark": is_mark, "pal": (ws[0] >> 12) if ws else 0})
            if not is_mark:
                s = "".join(kana8.get(f"{w & 0xFFF:03x}", "?") for w in ws)
                # 바로 앞 세그먼트가 탁점 행이면 해당 열에 합침
                marks = [sg for sg in segs[:i] if all((w & 0xFFF) == L.WORDREC_MARK for w in sg[1]) and (sg[0] - 0x200000) // 128 == off // 128 - 1]
                for md, mws in marks:
                    c0 = ((md - 0x200000) % 128) // 2 - (off % 128) // 2
                    for k in range(len(mws)):
                        j = c0 + k
                        if 0 <= j < len(s):
                            s = s[:j] + DAKU.get(s[j], s[j] + "゛") + s[j + 1:]
                texts[str(i)] = s
        records.append({"id": rid, "kind": "wordrec", "addr": f"{start:06x}", "rows": [], "source_text": texts,
                        "layout": {"segments": layout, "end": f"{end:06x}", "note": "텍스트 세그먼트별 한글(≤원문 길이 권장, 레코드 총 길이 제한). 탁점 세그먼트는 생략됨"}})
    for idx, rid in L.QUAD_RECORDS.items():
        start, end, segs = L.quad_record(img, idx)
        texts, lay = {}, []
        for i, (attr, dest, ws) in enumerate(segs):
            off = dest - 0x200000
            lay.append({"attr": attr, "dest": dest, "row": off // 128, "col": (off % 128) // 2, "len": len(ws)})
            texts[str(i)] = "".join(" " if w == 0 else L.QUAD_FONT_MAP.get(w, "?") for w in ws)
        records.append({"id": rid, "kind": "quad", "addr": f"{start:06x}", "rows": [], "source_text": texts,
                        "layout": {"segments": lay, "end": f"{end:06x}", "note": "쿼드(16×16=8×8×4) 대사. 세그먼트(줄)별 ≤20글자, 레코드 총 길이 제한. 쌍둥이 타일맵 레코드 " + L.QUAD_TWIN.get(rid, "")}})
    for idx, rid in L.ASCII_RECORDS.items():
        segs = L.ascii_record_segments(img, idx)
        records.append({"id": rid, "kind": "ascii", "addr": f"{idx:02x}", "rows": [],
                        "source_text": {str(i): sg[2].decode("latin1").rstrip("\x00") for i, sg in enumerate(segs)},
                        "layout": {"segments": [{"attr": sg[0], "dest": sg[1], "col": ((sg[1] - 0x200000) % 128) // 2, "row": (sg[1] - 0x200000) // 128, "len": len(sg[2].rstrip(b"\x00"))} for sg in segs],
                                   "note": "ASCII 프린터 레코드. 한글은 세그먼트별 원문 중앙에 맞춰 배치(길이는 자유)"}})
    SRC.write_text(json.dumps({"records": records}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] {SRC.name}: {len(records)} 레코드 (프로필 8 + 계급)")
    for rec in records:
        print(f"== {rec['id']} @{rec['addr']}")
        for r, t in rec["source_text"].items():
            if t.strip():
                print(f"  {int(r):2d} {t}")

    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in ledger["entries"]}
    added = 0
    for rec in records:
        if rec["id"] in by_id:
            e = by_id[rec["id"]]
            e["source_text"] = rec["source_text"]
            e["layout"] = rec["layout"]
            continue
        ledger["entries"].append({"id": rec["id"], "label": f"profile {rec['block_index']}" if rec["kind"] == "profile" else ("rank names" if rec["kind"] == "rank" else f"{rec['kind']} record {rec['addr']}"), "kind": rec["kind"], "addr": rec["addr"],
                                  "source_text": rec["source_text"], "layout": rec["layout"], "ko_rows": [], "ko_cells": {},
                                  "status": "untranslated", "notes": ""})
        added += 1
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] ledger: profile 항목 {added} 추가 (총 {len(ledger['entries'])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
