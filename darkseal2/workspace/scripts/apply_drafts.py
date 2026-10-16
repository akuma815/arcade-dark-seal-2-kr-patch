"""2편 초벌/수정 파일을 원장에 반영하고 레이아웃을 검사한다.

검사: 행 수 ≤ 레코드 행 수, 비어있지 않은 행은 span 이 있어야 하며 셀 수 ≤ span 폭, 문자는 한글/원문 표의 문장부호/ASCII 숫자.
사용: python darkseal2/workspace/scripts/apply_drafts.py darkseal2/workspace/text/translation/drafts_v1.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ds2lib as L  # noqa: E402

LEDGER = L.GAME / "workspace" / "text" / "translation" / "ds2_translation.json"
MAP = L.GAME / "workspace" / "font" / "mapping" / "ds2_glyph_map.json"
HANDMADE = set(",.()?!")


def is_hangul(c):
    return 0xAC00 <= ord(c) <= 0xD7A3


def main() -> int:
    drafts = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    reusable = set(json.loads(MAP.read_text(encoding="utf-8")).values())
    by_id = {e["id"]: e for e in ledger["entries"]}
    problems, hangul = [], Counter()
    for sid, d in drafts.items():
        if sid.startswith("_") or sid not in by_id:
            continue
        e = by_id[sid]
        if e.get("kind") == "profile":
            lay = e["layout"]
            cells = {}
            for r, segs in d.get("ko_cells", {}).items():
                r = int(r)
                span = lay["stat_rows"].get(str(r)) or lay["stat_rows"].get(r)
                if r == lay.get("title_row") or r == 16:
                    span = [1, 38]
                if span is None:
                    problems.append(f"{sid} 행{r}: 스탯/제목 행이 아님")
                    continue
                for col, text in segs:
                    if col + len(text) - 1 > span[1]:
                        problems.append(f"{sid} 행{r}: 열{col}+{len(text)}셀 > {span[1]}: {text}")
                    for c in text:
                        if is_hangul(c):
                            hangul[c] += 1
                cells[str(r)] = segs
            b0, b1 = lay["body_rows"]
            c0, c1 = lay["body_cols"]
            width = c1 - c0 + 1
            lines = []
            for para in d.get("ko_body", []):
                words = para.split(" ")
                cur = " " + words[0]            # 단락 첫 줄 들여쓰기 1칸(원문과 동일)
                for word in words[1:]:
                    cand = cur + " " + word
                    if len(cand) > width:
                        lines.append(cur)
                        cur = word
                    else:
                        cur = cand
                lines.append(cur)
            for ln in lines:
                if len(ln) > width:
                    problems.append(f"{sid}: 본문 한 단어가 {width}셀 초과: {ln}")
            body_rows = list(range(b0 + 1, b1 + 1, 2))          # 짝수 행(원문 위치) — 줄 간격을 모든 인물에서 같게 유지
            if len(lines) > len(body_rows):
                problems.append(f"{sid}: 본문 {len(lines)}줄 > 가용 {len(body_rows)}줄(행 간격 2) — 문장을 줄일 것: {[len(l) for l in lines]}")
            for i, ln in enumerate(lines[:len(body_rows)]):
                cells[str(body_rows[i])] = [[c0, ln]]
                for c in ln:
                    if is_hangul(c):
                        hangul[c] += 1
            e["ko_cells"] = cells
            e["ko_rows"] = lines
            e["status"] = "draft"
            if d.get("notes"):
                e["notes"] = d["notes"]
            continue
        rows = d["ko_rows"]
        if e.get("kind") == "sky":
            p0, p1 = e["layout"]["panel_rows"]
            r0 = e["layout"].get("text_row0", p0)
            if len(rows) > p1 - r0 + 1:
                problems.append(f"{sid}: 패널 {p1 - r0 + 1}줄 < {len(rows)}줄")
            if len(rows) > 15:
                problems.append(f"{sid}: 화면에 보이는 줄은 15줄(행 {r0}~{r0 + 14}) — {len(rows)}줄")
            for i, row in enumerate(rows):
                if len(row) > 20:
                    problems.append(f"{sid} 줄{i}: {len(row)}셀 > 20: {row}")
                for c in row:
                    if is_hangul(c):
                        hangul[c] += 1
            if d.get("ko_box_row"):
                e["ko_box_row"] = d["ko_box_row"]
                for c in d["ko_box_row"]:
                    if is_hangul(c):
                        hangul[c] += 1
            e["ko_rows"] = rows
            e["status"] = "draft"
            if d.get("notes"):
                e["notes"] = d["notes"]
            continue
        if len(rows) > e["nrows"]:
            problems.append(f"{sid}: {len(rows)}행 > 레코드 {e['nrows']}행")
        for i, row in enumerate(rows):
            if not row:
                continue
            span = e["layout"]["rows"][i]["span"] if i < len(e["layout"]["rows"]) else None
            if span is None:
                problems.append(f"{sid} 행{i}: 텍스트 불가 행(span 없음): {row}")
                continue
            width = span[1] - span[0] + 1
            if len(row) > width:
                problems.append(f"{sid} 행{i}: {len(row)}셀 > span {width} ({span}): {row}")
            for c in row:
                if c == " ":
                    continue
                if is_hangul(c):
                    hangul[c] += 1
                elif c in reusable or c in HANDMADE or c.isdigit():
                    pass
                else:
                    problems.append(f"{sid} 행{i}: 공급 불가 문자 '{c}'")
        e["ko_rows"] = rows + [""] * 0
        e["status"] = "draft"
        if d.get("notes"):
            e["notes"] = d["notes"]
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(1 for e in ledger["entries"] if e["status"] == "draft")
    print(f"[OK] ledger updated: draft={n}/{len(ledger['entries'])}, 고유 한글 {len(hangul)}자 (출현 {sum(hangul.values())})")
    for p in problems:
        print("  [!]", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
