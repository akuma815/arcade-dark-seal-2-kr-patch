"""Dark Seal 2 PoC 빌드: 메시지 블록 첫 줄(프롤로그 1행)을 한글 그림 글자로 바꿔 FBNeo IPS 로 띄운다.

절차
 1. 원본 로드, 무변경 왕복(프로그램 인터리브, gfx2 복호→타일 디코드→인코드→암호화) 바이트 동일 검사
 2. 첫 줄 글리프 타일(원본 일본어, PoC 한정 덮어쓰기)에 Galmuri11 한글 기록
 3. 타일맵 블록 0xa4954 행 0 의 셀을 새 타일로 재작성 — 미러 2벌 모두
 4. Expected Write → build/poc/ 에 ROM·IPS·dat → FBNeo support/ips/darkseal2/ 설치
사용: python darkseal2/workspace/scripts/build_poc.py [--no-install]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ds2lib as L  # noqa: E402
from patchutil import check_allowed, crc32, ips_build  # noqa: E402  (ds2lib 이 common/scripts 를 path 에 넣음)

FONT16 = L.ROOT.parent.parent / "Font" / "Galmuri11_16x16.png"
BUILD = L.GAME / "build" / "poc"
FBNEO_IPS = Path(r"H:\FBNeo v1.0.0.03\support\ips\darkseal2")
POC_NAME = "poc"

POC_ROW = 0
POC_COL0 = 2
POC_TEXT = "갈리아력 삼오오년 칠월"        # 12셀 (원본 행 0 = x 2..13)
# PoC 전용: 행 0 이 쓰는 원본 글리프 타일을 덮어쓴다 (다른 곳의 같은 글자도 바뀜 — PoC 한정)
POC_TILES = [0xA59, 0xA5A, 0xA5B, 0xA5C, 0xA55, 0xA5D, 0xA5E, 0xA60, 0xA61]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-install", action="store_true")
    a = ap.parse_args()

    prg_files, gfx_files = L.load_originals()
    img = L.prg_decode(prg_files)
    assert L.prg_encode(img) == prg_files, "프로그램 왕복 실패"
    assert img[0x80000:0x100000] == img[0x100000:0x180000], "mas12/13 미러 가정 실패"
    enc = L.gfx2_load(gfx_files)
    plain = L.D.deco74_decrypt(enc)
    tiles = L.D.decode_tiles_16x16(plain)
    re_plain = bytearray(len(plain))
    L.D.encode_tiles_16x16(tiles, re_plain)
    assert bytes(re_plain) == plain, "16×16 타일 왕복 실패"
    assert L.D.deco74_encrypt(plain) == enc, "DECO74 왕복 실패"
    print("[OK] 무변경 왕복: 프로그램 6파일, gfx2 복호/디코드/인코드/암호화")

    # 글리프
    sheet = Image.open(FONT16).convert("RGBA")
    chars = []
    for c in POC_TEXT:
        if c != " " and c not in chars:
            chars.append(c)
    if len(chars) > len(POC_TILES):
        raise SystemExit("PoC 타일 부족")
    glyph_tile = {}
    for c, t in zip(chars, POC_TILES):
        m11 = L.hangul_sheet_glyph(sheet, c, 16)
        mask = [[0] * 16 for _ in range(16)]
        for y in range(11):
            for x in range(11):
                mask[y + 2][x + 2] = m11[y][x]
        tiles[t] = L.mask_to_glyph(mask)
        glyph_tile[c] = t
    print(f"[OK] 글리프 {len(chars)}자 → 타일 {', '.join(f'{t:03x}' for t in glyph_tile.values())}")

    # 타일맵
    new_img = bytearray(img)
    for k, c in enumerate(POC_TEXT):
        col = POC_COL0 + k
        word = 0 if c == " " else glyph_tile[c]
        for mirror in (0, L.MIRROR):
            off = L.msg_cell_offset(POC_ROW, col) + mirror
            new_img[off:off + 2] = word.to_bytes(2, "big")
    # 허용 범위 = 행 0 의 셀 구간(인접 셀 변경이 한 런으로 합쳐지므로 구간 단위로 선언)
    allowed_prg = [(L.msg_cell_offset(POC_ROW, POC_COL0) + m, L.msg_cell_offset(POC_ROW, POC_COL0 + len(POC_TEXT)) + m)
                   for m in (0, L.MIRROR)]
    check_allowed(img, bytes(new_img), allowed_prg, "prg")

    new_plain = bytearray(len(plain))
    L.D.encode_tiles_16x16(tiles, new_plain)
    half = len(plain) // 2
    allowed_plain = []
    for t in POC_TILES:
        allowed_plain += [(t * 64, t * 64 + 64), (half + t * 64, half + t * 64 + 64)]
    check_allowed(plain, bytes(new_plain), allowed_plain, "gfx2 plain")
    new_enc = L.D.deco74_encrypt(bytes(new_plain))
    print("[OK] Expected Write: 타일맵 셀 %d개×미러2, 타일 %d개" % (len(POC_TEXT), len(POC_TILES)))

    # 출력
    BUILD.mkdir(parents=True, exist_ok=True)
    orig_all = {**prg_files, **gfx_files}
    new_all = {**L.prg_encode(bytes(new_img)), **L.gfx2_split(new_enc)}
    dat_lines = []
    report = {"glyph_tile": {c: f"{t:03x}" for c, t in glyph_tile.items()}, "roms": {}}
    for name, data in new_all.items():
        fname = name.split("/")[-1]
        (BUILD / fname).write_bytes(data)
        if data != orig_all[name]:
            ips_name = f"{POC_NAME}-{fname.replace('.', '_')}"
            (BUILD / f"{ips_name}.ips").write_bytes(ips_build(orig_all[name], data))
            dat_lines.append(f"{fname}\t{ips_name}\tCRC({crc32(orig_all[name])})")
            report["roms"][fname] = {"changed_bytes": sum(1 for x, y in zip(orig_all[name], data) if x != y), "ips": ips_name + ".ips"}
    (BUILD / f"{POC_NAME}.dat").write_text("\n".join(dat_lines) + "\n\n[en_US]\nDark Seal 2 Korean PoC\n\n[ko_KR]\n다크씰 2 한글 PoC\n", encoding="utf-8")
    (BUILD / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[OK] build:", ", ".join(f"{k} ({v['changed_bytes']}B)" for k, v in report["roms"].items()))
    if not a.no_install:
        FBNEO_IPS.mkdir(parents=True, exist_ok=True)
        for f in [BUILD / f"{POC_NAME}.dat"] + list(BUILD.glob(f"{POC_NAME}-*.ips")):
            shutil.copy(f, FBNEO_IPS / f.name)
        print("[OK] FBNeo support/ips/darkseal2/ 에 설치:", POC_NAME)
    return 0


if __name__ == "__main__":
    sys.exit(main())
