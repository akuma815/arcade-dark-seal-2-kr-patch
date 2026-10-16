"""Dark Seal 2 텍스트 추출기: 메시지 타일맵 블록(0xa4950, 20열)을 레코드(연속 비공백 행 묶음)로 나눠 JSON 으로 쓴다.

출력: workspace/text/source/ds2_blocks.json
  records[i] = {id: "M:<행시작>", rows: [[tile hex × 20] …], row0, nrows, tiles(고유)}
또 글리프 뱅크(0x9c0~0xb3f) 사용 통계를 남긴다.
사용: python darkseal2/workspace/scripts/extract_text.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ds2lib as L  # noqa: E402

OUT = L.GAME / "workspace" / "text" / "source" / "ds2_blocks.json"
MSG_END = 0xA8800          # 메시지 블록 끝 후보 (0xa7f5a 뒤에도 상자 행이 이어짐 — 레코드 분할로 확인)
TEXT_BANK = (0x9C0, 0xB60)
FONT2 = (0xDC2, 0xE9C)       # 제2 글자 영역: NPC·엔딩·스태프롤 (스태프롤 전용 0xe09~0xe10 포함)
# 메시지 블록 밖의 텍스트 영역: (라벨, 20열 행 base, 행 수, 종류)
#  sky    : 하늘 배경 세로쓰기 스토리(0xa39fe) — 열 단위 세로 텍스트 + 하단 상자 1줄. 한글은 검은 패널 위 가로쓰기로 재배치
#  line   : NPC 대사 행(빈칸 0, 배경은 아래 레이어)
#  ending : 엔딩 메시지(파란 상자, 채움 타일 = 가장 흔한 비글자 타일)
EXTRA_REGIONS = [
    ("sky", 0xA39D8, 33, "sky"),
    ("npc[0]", 0xAB570, 4, "line"), ("npc[1]", 0xABF70, 2, "line"), ("npc[2]", 0xAC240, 3, "line"),
    ("ending[0]", 0xAEAB8, 2, "ending"), ("ending[1]", 0xAED38, 3, "ending"),
    # 2026-10-04 추가: 게임 중 메시지(석판 힌트·보스 대사) — 블록 0xa8800 이후 20열 행 재스캔으로 발견
    ("tablet", 0xAAB98, 3, "line"), ("boss[0]", 0xAADF0, 2, "line"), ("boss[1]", 0xAB070, 1, "line"), ("boss[2]", 0xAB2F0, 1, "line"),
    ("boss[3]", 0xAB7F0, 3, "line"), ("boss[4]", 0xABA70, 2, "line"), ("boss[5]", 0xABCF0, 4, "line"), ("boss[6]", 0xAC1F0, 2, "line"),
    ("boss[7]", 0xAC470, 2, "line"),
    # 스태프롤(原作・脚本…, 0xe05~0xe90 + 가나 일부) — 일본어 유지 결정. 타일 보존을 위해 레코드로 등록(번역 안 함)
    ("credits", 0xAC600, 224, "credits"),
]


def is_font(t: int) -> bool:
    return 0xA03 <= t <= 0xB4B or FONT2[0] <= t < FONT2[1]


def main() -> int:
    prg_files, _ = L.load_originals()
    img = L.prg_decode(prg_files)
    nrows = (MSG_END - L.MSG_BLOCK) // (L.MSG_COLS * 2) + 1
    rows = []
    for r in range(nrows):
        off = L.MSG_BLOCK + r * L.MSG_COLS * 2
        rows.append([int.from_bytes(img[off + c * 2:off + c * 2 + 2], "big") for c in range(L.MSG_COLS)])
    use: Counter = Counter()
    records = []
    r = 0
    while r < nrows:
        if any(rows[r]):
            s = r
            while r < nrows and any(rows[r]):
                r += 1
            rec_rows = rows[s:r]
            tiles = sorted({w & 0xFFF for row in rec_rows for w in row if w})
            for row in rec_rows:
                for w in row:
                    if w:
                        use[w & 0xFFF] += 1
            text_tiles = [t for t in tiles if TEXT_BANK[0] <= t < TEXT_BANK[1]]
            records.append({"id": f"M:{s:03d}", "row0": s, "nrows": r - s, "addr": f"{L.MSG_BLOCK + s * L.MSG_COLS * 2:06x}",
                            "rows": [[f"{w:04x}" for w in row] for row in rec_rows],
                            "unique_tiles": len(tiles), "text_tiles": len(text_tiles),
                            "pal": sorted({w >> 12 for row in rec_rows for w in row if w})})
        else:
            r += 1
    for label, base, nr, kind in EXTRA_REGIONS:
        rec_rows = [[int.from_bytes(img[base + r * 40 + c * 2:base + r * 40 + c * 2 + 2], "big") for c in range(L.MSG_COLS)] for r in range(nr)]
        tiles = sorted({w & 0xFFF for row in rec_rows for w in row if w})
        for row in rec_rows:
            for w in row:
                if w:
                    use[w & 0xFFF] += 1
        fill = Counter(w & 0xFFF for row in rec_rows for w in row if w and not is_font(w & 0xFFF)).most_common(1)
        records.append({"id": f"X:{base:06x}", "label": label, "kind": kind, "row0": None, "nrows": nr, "addr": f"{base:06x}",
                        "rows": [[f"{w:04x}" for w in row] for row in rec_rows],
                        "unique_tiles": len(tiles), "text_tiles": sum(1 for t in tiles if is_font(t)),
                        "pal": sorted({w >> 12 for row in rec_rows for w in row if w}),
                        "fill_tile": f"{fill[0][0]:03x}" if fill else None})
    out = {"source": "darkseal2 mas12/13 message block + extra text regions", "block": f"{L.MSG_BLOCK:06x}", "cols": L.MSG_COLS, "nrows": nrows,
           "records": records, "tile_usage": {f"{k:03x}": v for k, v in sorted(use.items())}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] {OUT.relative_to(L.ROOT)}: rows={nrows} records={len(records)} unique tiles={len(use)} "
          f"text-bank tiles={sum(1 for t in use if TEXT_BANK[0] <= t < TEXT_BANK[1])}")
    for rec in records:
        print(f"  {rec['id']:<10} {rec.get('label', ''):<10} rows+{rec['nrows']:2d} uniq={rec['unique_tiles']:3d} text={rec['text_tiles']:3d} pal={rec['pal']} fill={rec.get('fill_tile')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
