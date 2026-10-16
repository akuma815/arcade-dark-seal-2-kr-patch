"""2편 번역 원장(SSOT) 생성/갱신: workspace/text/translation/ds2_translation.json

레코드(메시지 블록의 연속 행 묶음)마다:
  - source_rows: 복원 원문(행별). 텍스트 뱅크 글리프 = 문자, 상자 내부 빈칸(0xa88) = '　', 틀/기타 타일 = '▣'
  - layout.rows[i] = {"span": [c0, c1]}  텍스트를 놓을 수 있는 열 범위(원문의 글자·내부 빈칸 열), 없으면 null
  - ko_rows: 번역 행 목록(행 수 = 원문 행 수, 각 행은 span 폭 이하). 공백 1자 = 빈 셀
  - status: untranslated | draft | needs_review | approved
사용: python darkseal2/workspace/scripts/make_ledger.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ds2lib as L  # noqa: E402

SRC = L.GAME / "workspace" / "text" / "source"
MAP = L.GAME / "workspace" / "font" / "mapping" / "ds2_glyph_map.json"
LEDGER = L.GAME / "workspace" / "text" / "translation" / "ds2_translation.json"
TEXT_BANK = (0x9C0, 0xB60)
FONT2 = (0xDCF, 0xE9C)
BOX_BLANK = 0xA88


def is_font(t: int) -> bool:
    return 0xA03 <= t <= 0xB4B or FONT2[0] <= t < FONT2[1]


def extra_entry(rec: dict, m: dict, keep: dict) -> dict:
    """메시지 블록 밖 영역 레코드. sky: 세로 열을 읽기 순서(오른쪽 열부터, 위→아래)로 복원해 source_text 에 둔다."""
    rows = [[int(h, 16) for h in row] for row in rec["rows"]]
    fill = int(rec["fill_tile"], 16) if rec.get("fill_tile") else 0
    src_rows, spans = [], []
    for row in rows:
        s, cols = "", []
        for c, w in enumerate(row):
            t = w & 0xFFF
            if w == 0:
                s += "　"
                if rec["kind"] in ("line", "sky"):
                    cols.append(c)
            elif t == fill and rec["kind"] == "ending":
                s += "　"
                cols.append(c)
            elif is_font(t) and f"{t:03x}" in m and m[f"{t:03x}"] != "▣":
                s += m[f"{t:03x}"]
                cols.append(c)
            else:
                s += "▣"
        src_rows.append(s)
        spans.append([min(cols), max(cols)] if cols else None)
    e = {"id": rec["id"], "label": rec["label"], "kind": rec["kind"], "nrows": rec["nrows"], "addr": rec["addr"],
         "source_rows": src_rows, "layout": {"box": rec["kind"] == "ending", "rows": [{"span": sp} for sp in spans], "fill_tile": rec.get("fill_tile")},
         "ko_rows": keep.get(rec["id"], {}).get("ko_rows", []), "status": keep.get(rec["id"], {}).get("status", "untranslated"),
         "notes": keep.get(rec["id"], {}).get("notes", "")}
    if rec["kind"] == "sky":
        # 세로쓰기: 글자가 있는 열을 오른쪽부터, 각 열은 위→아래. 행 범위는 글자 행만
        text_rows = [i for i, row in enumerate(rows) if any(w and is_font(w & 0xFFF) for w in row)]
        cols_with = sorted({c for i in text_rows for c, w in enumerate(rows[i]) if w and is_font(w & 0xFFF)}, reverse=True)
        columns = []
        for c in cols_with:
            col = "".join(m.get(f"{rows[i][c] & 0xFFF:03x}", "") for i in text_rows if rows[i][c] and is_font(rows[i][c] & 0xFFF))
            columns.append(col)
        e["source_vertical_columns"] = columns
        e["layout"]["panel_rows"] = [text_rows[0], text_rows[-1]]
        e["layout"]["text_row0"] = 1    # 화면에 온전히 보이는 첫 행(행 0 은 화면 위 — 원문 세로 텍스트도 행 1~15 사용)
        e["layout"]["note"] = "한글은 panel_rows 범위를 채움 타일(검정)로 덮고 가로쓰기(행당 ≤20셀). ko_rows 의 i번째 줄 = text_row0+i 행"
    return e


def main() -> int:
    blocks = json.loads((SRC / "ds2_blocks.json").read_text(encoding="utf-8"))
    m = json.loads(MAP.read_text(encoding="utf-8"))
    old = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {"entries": []}
    keep = {e["id"]: e for e in old.get("entries", [])}
    entries = []
    for rec in blocks["records"]:
        if rec["id"].startswith("X:"):
            entries.append(extra_entry(rec, m, keep))
            continue
        src_rows, spans, has_text = [], [], False
        for row in rec["rows"]:
            s = ""
            cols = []
            for c, h in enumerate(row):
                w = int(h, 16)
                t = w & 0xFFF
                if w == 0:
                    s += "　"
                    cols.append(c) if any(int(x, 16) for x in row) and rec["row0"] < 23 else None   # 프롤로그(상자 없음): 0 도 텍스트 칸
                elif t == BOX_BLANK:
                    s += "　"
                    cols.append(c)
                elif TEXT_BANK[0] <= t < TEXT_BANK[1] and f"{t:03x}" in m and m[f"{t:03x}"] != "▣":
                    s += m[f"{t:03x}"]
                    cols.append(c)
                    has_text = True
                else:
                    s += "▣"
            src_rows.append(s)
            spans.append([min(cols), max(cols)] if cols else None)
        if not has_text:
            continue
        box = rec["row0"] >= 23
        entries.append({
            "id": rec["id"], "row0": rec["row0"], "nrows": rec["nrows"], "addr": rec["addr"],
            "source_rows": src_rows,
            "layout": {"box": box, "rows": [{"span": sp} for sp in spans],
                       "note": "상자 레코드: 틀(▣)은 유지, span 안에만 글자/빈칸. 프롤로그: span = 원문 글자 범위(0열부터 19열까지 확장 가능)"},
            "ko_rows": keep.get(rec["id"], {}).get("ko_rows", []),
            "status": keep.get(rec["id"], {}).get("status", "untranslated"),
            "notes": keep.get(rec["id"], {}).get("notes", ""),
        })
    out = {"_schema": "ds2_translation v1", "entries": entries}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] {LEDGER.relative_to(L.ROOT)}: entries={len(entries)}")
    for e in entries:
        sp = [r["span"] for r in e["layout"]["rows"]]
        print(f"  {e['id']} rows={e['nrows']} box={e['layout']['box']} spans={sp} status={e['status']}")
        if e.get("source_vertical_columns"):
            print("     세로 열(오른쪽부터):", " / ".join(e["source_vertical_columns"]))
        if e["id"].startswith("X:"):
            for s in e["source_rows"]:
                if s.strip("　▣"):
                    print("     ", s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
