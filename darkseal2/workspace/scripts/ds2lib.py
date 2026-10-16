"""Dark Seal 2 (darkseal2) 형식 라이브러리 — docs/survey.md 의 규칙을 코드로 고정한다.

- 프로그램/데이터 영역 0x000000~0x17ffff: (jb-01-3.3d 상위 + jb-00-3.3a 하위) @0, (jb-03.5d + jb-02.5a) @0x40000,
  (부모 mas13 상위 + mas12 하위) @0x80000. 스크램블 없음. mas12/13 은 256KB 미러 2벌(0x80000~0xfffff == 0x100000~0x17ffff).
- gfx2 (레이어 2/3 의 16×16 타일) = 부모 mas02 @0 + mas03 @0x80000 → DECO 74 복호 → deco16 16×16 디코드. 8192 타일.
- 텍스트 타일맵 워드 = pal<<12 | tile(12bit) (+ 레이어 뱅크 비트, 프롤로그는 뱅크 0). 메시지 블록 0xa4950: 20열 행.
- 글리프 픽셀: 본체 7(흰), 외곽선 2(검정) — 레이어 2 팔레트 0x200+.
"""
from __future__ import annotations

import sys
from pathlib import Path

GAME = Path(__file__).resolve().parents[2]          # darkseal2/
ROOT = GAME.parent
EXTRACTED = GAME / "extracted"
sys.path.insert(0, str(ROOT / "common" / "scripts"))
import deco74 as D  # noqa: E402

PRG_FILES = [  # (상대경로, base, 0=상위/1=하위)
    ("jb-01-3.3d", 0x000000, 0), ("jb-00-3.3a", 0x000000, 1),
    ("jb-03.5d", 0x040000, 0), ("jb-02.5a", 0x040000, 1),
    ("parent/mas13", 0x080000, 0), ("parent/mas12", 0x080000, 1),
]
GFX2_FILES = [("parent/mas02", 0x00000), ("parent/mas03", 0x80000)]
GFX0_FILES = ("jb-04.10d", "jb-05.12d")   # 8×8 문자 ROM (짝수/홀수 인터리브 → DECO 74) — 클론 고유 ROM. 4096 타일
# 프로필 화면(어트랙트 루틴 0x3c7a/0x3dc4, 로더 0x1045a): 40열×32행 8×8 타일맵 블록을 pf0(0x200000, 행 간격 128B)에 복사.
# 포인터 배열 = *(0x9c27c+0xc) = 0xb5288, 12개. 블록 4~8 = 5인(스탯 포함), 9~11 = 3인(본문만). 워드 = pal<<12 | 타일(직접 인덱스)
PROFILE_PTR_TABLE = 0xB5288
PROFILE_BLOCKS = 12
PROFILE_COLS, PROFILE_ROWS = 40, 32
PROFILE_FONT = (0xEB8, 0xF7A)              # 프로필 글자 타일 범위(라벨·가나·숫자)
PROFILE_FREE_TILES = (0x928, 0xC00)        # 문자 ROM 빈 타일 연속 구간(0xc00 은 상자 채움으로 사용 중 — 제외)
PROFILE_PX_BODY, PROFILE_PX_SHADOW = 1, 2  # 원본 가나 글리프: 본체 1, 우·하 그림자 2
# 프로필 P4(카를)만 ASCII 메시지 프린터 0x4c28(표 0x4c92, 인덱스 0x8c → 레코드 0x7ca0 = attr.w, dest.l=0x20072c, 바이트열, ff ff)
# 로 "Morning Star" 를 행 14 열 22 에 덧그린다(블록의 "Mornig" 오타 보정용). 텍스트 첫 2바이트를 종료 코드로 바꿔 무효화한다.
PROFILE_OVERLAY_PATCH = (0x7CA6, b"Mo", b"\xff\xff")
# 계급명(루틴 0x2410, 플레이어 구조 0xfdc034+8n 의 +3 = 계급 0~5): 표 0x251c(6 long) → 6바이트 ASCII 문자열을 pf0 에 바이트=타일로 복사
# (0x2470 `move.b (a1)+,d1 / move.w d1,(a2)+`). 한글은 16비트 워드 문자열이 필요하므로 복사를 `move.w (a1)+,(a2)+` 로 바꾸고
# 프로그램 ROM 빈 공간(0x3b022~0x3ffff, 0xff) 끝에 6×6 워드 문자열을 두어 표를 재지정한다. 빈칸 = 0x0020(ASCII 공백 타일).
RANK_TABLE = 0x251C
RANK_COUNT, RANK_CELLS = 6, 6
RANK_COPY_PATCH = (0x2470, bytes.fromhex("121934c1"), bytes.fromhex("34d94e71"))
RANK_NEW_STRINGS = 0x3FF00
RANK_BLANK = 0x0020
# ASCII 메시지 프린터 0x4c28: 표 0x4c92 → 레코드 [attr.w][dest.l][바이트…][ff fe → 다음 세그먼트 attr/dest][ff ff 끝], 타일 = attr | 바이트.
# attr 0x0900 이면 바이트 0x28~0xfe → 타일 0x928~0x9fe 이므로 그 구간을 ASCII 레코드용 한글 글리프에 쓴다(0x928 = 공백 유지).
# 번역 대상: 0x3b "LEGENDARY HEROES"(랭킹 제목), 0x3c 직업 라벨 5개. 새 레코드는 빈 공간 0x3fd00~ 에 두고 표를 재지정.
ASCII_TABLE = 0x4C92
ASCII_RECORDS = {0x3B: "AS:3b", 0x3C: "AS:3c", 0x3D: "AS:3d", **{i: f"AS:{i:02x}" for i in range(0x08, 0x14)}}   # 0x3d = SELECT YOUR CHARACTER / TIME   # 0x08~0x13 = 상태이상(POISON…) P1/P2, pal 5
ASCII_GLYPH_RANGE = (0x929, 0x9FF)
ASCII_SPACE_TILE = 0x928
ASCII_ATTR = 0x0900
ASCII_NEW_RECORDS = 0x3FD00
# 워드 레코드(캐릭터 선택 설명문): 루틴 0xa5e0 부근이 표 0xa614 → 레코드 [dest.l][워드…][fffe → 다음 dest][ffff 끝] 을 pf0 에 복사.
# 워드 = pal<<12|타일(8×8 가나 0x0ee~0x11e). 한글은 같은 자리(0xa61c~0xa6d9, 190B)에 제자리 재기록 — 탁점 세그먼트는 제거.
WORDREC_RECORDS = {0xA61C: ("WR:a61c", 0xA6DA)}
WORDREC_MARK = 0x11E


def wordrec_segments(img: bytes, start: int) -> list[tuple[int, list[int]]]:
    import struct
    out, o = [], start
    while True:
        dest = struct.unpack_from(">I", img, o)[0]; o += 4
        ws = []
        while True:
            w = struct.unpack_from(">H", img, o)[0]; o += 2
            if w in (0xFFFE, 0xFFFF):
                break
            ws.append(w)
        out.append((dest, ws))
        if w == 0xFFFF:
            return out


def ascii_record_segments(img: bytes, idx: int) -> list[tuple[int, int, bytes]]:
    """레코드 idx 의 세그먼트 [(attr, dest, bytes)]."""
    import struct
    rec = struct.unpack_from(">I", img, ASCII_TABLE + 4 * idx)[0]
    out, o = [], rec
    while True:
        attr = struct.unpack_from(">H", img, o)[0]
        dest = struct.unpack_from(">I", img, o + 2)[0]
        o += 6
        cur = bytearray()
        while not (img[o] == 0xFF and img[o + 1] in (0xFE, 0xFF)):
            cur.append(img[o]); o += 1
        out.append((attr, dest, bytes(cur)))
        if img[o + 1] == 0xFF:
            return out
        o += 2


def profile_block_addrs(img: bytes) -> list[int]:
    import struct
    return [struct.unpack_from(">I", img, PROFILE_PTR_TABLE + 4 * i)[0] for i in range(PROFILE_BLOCKS)]


def hangul8_tile(mask: list[list[int]], body: int = PROFILE_PX_BODY, shadow: int = PROFILE_PX_SHADOW) -> list[list[int]]:
    """8×8 마스크(7×7 글리프, 좌상단 기준) → 본체 + 우/하/우하 그림자 타일."""
    t = [[0] * 8 for _ in range(8)]
    for y in range(8):
        for x in range(8):
            if mask[y][x]:
                t[y][x] = body
    for y in range(8):
        for x in range(8):
            if not t[y][x] and any(0 <= y - dy < 8 and 0 <= x - dx < 8 and mask[y - dy][x - dx] for dy, dx in ((0, 1), (1, 0), (1, 1))):
                t[y][x] = shadow
    return t
MSG_BLOCK = 0xA4950          # 메시지 화면 타일맵 블록: 20열 행(화면 폭 20셀), 행 0 = [0,0,ガ,リ,ア,…]. PoC-1 로 실측
MSG_COLS = 20
MIRROR = 0x80000             # mas12/13 두 번째 사본 오프셋
GLYPH_PX_BODY = 7
GLYPH_PX_OUTLINE = 2

# 하늘 스토리 장면 루틴(0x1caa~0x1dfe, 어트랙트). 원본은 텍스트 레이어 X(long 0xfdc17c, 16.16 고정소수)를 0x140 에서
# 매 프레임 -0x4000(-0.25px) 씩 1280프레임 내려 0 에 닿으면(루프 종료 조건은 0xfdc16c 의 0x3ff 랩) 0x80프레임 유지 후 페이드.
# 가로 패널(열 0~19)은 X=0 에서만 온전히 보이므로 시작 X=0·이동량 0 으로 고정하고 유지 시간을 늘린다. 명령 길이는 그대로.
SKY_SCENE_PATCHES = [  # (주소, 원본 바이트, 패치 바이트)
    (0x1CFA, bytes.fromhex("23fc0140000000fdc17c"), bytes.fromhex("23fc0000000000fdc17c")),  # move.l #$1400000 → #0
    (0x1D8E, bytes.fromhex("04b90000400000fdc17c"), bytes.fromhex("04b90000000000fdc17c")),  # subi.l #$4000 → #0
    (0x1DBE, bytes.fromhex("3e3c0080"), bytes.fromhex("3e3c0200")),                          # 유지 0x80 → 0x200 프레임
    # 텍스트 레이어 Y: 원본 0x1fc 에서 블록 행 r 의 셀 위 = 16r−20 (캡처 실측: 행 2 글리프 띠 y14~25, Y+2 시 2px 위로 이동).
    # 15줄을 행 1~15 에 두므로 4px 내려(0x1f8) 행 1~15 가 y0~240 에 정확히 맞게 한다.
    (0x1D04, bytes.fromhex("33fc01fc00fdc180"), bytes.fromhex("33fc01f800fdc180")),          # Y 0x1fc → 0x1f8
]


def prg_decode(files: dict[str, bytes]) -> bytes:
    img = bytearray(0x180000)
    for name, base, off in PRG_FILES:
        d = files[name]
        img[base + off:base + off + 2 * len(d):2] = d
    return bytes(img)


def prg_encode(img: bytes) -> dict[str, bytes]:
    out = {}
    for name, base, off in PRG_FILES:
        size = 0x80000 if name.startswith("parent/") else 0x20000
        out[name] = img[base + off:base + off + 2 * size:2]
    return out


def gfx2_load(files: dict[str, bytes]) -> bytes:
    """암호화 상태의 gfx2 영역 (mas02 + mas03)."""
    return files["parent/mas02"] + files["parent/mas03"]


def gfx2_split(enc: bytes) -> dict[str, bytes]:
    return {"parent/mas02": enc[:0x80000], "parent/mas03": enc[0x80000:]}


def load_originals() -> tuple[dict[str, bytes], dict[str, bytes]]:
    prg = {name: (EXTRACTED / name).read_bytes() for name, _, _ in PRG_FILES}
    gfx = {name: (EXTRACTED / name).read_bytes() for name, _ in GFX2_FILES}
    for name in GFX0_FILES:
        gfx[name] = (EXTRACTED / name).read_bytes()
    return prg, gfx


def msg_cell_offset(row: int, col: int) -> int:
    return MSG_BLOCK + (row * MSG_COLS + col) * 2


def hangul_sheet_glyph(sheet, ch: str, cell: int = 16) -> list[list[int]]:
    i = ord(ch) - 0xAC00
    if not 0 <= i < 11172:
        raise KeyError(ch)
    x, y = (i % 64) * cell, (i // 64) * cell
    c = sheet.crop((x, y, x + cell, y + cell))
    return [[1 if c.getpixel((xx, yy))[1] > 127 else 0 for xx in range(cell)] for yy in range(cell)]


def mask_to_glyph(mask: list[list[int]], body: int = GLYPH_PX_BODY, outline: int | None = GLYPH_PX_OUTLINE) -> list[list[int]]:
    h, w = len(mask), len(mask[0])
    out = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                out[y][x] = body
    if outline is not None:
        for y in range(h):
            for x in range(w):
                if not out[y][x] and any(0 <= y + dy < h and 0 <= x + dx < w and mask[y + dy][x + dx]
                                         for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                    out[y][x] = outline
    return out

# 쿼드(2×2 8×8) 대사 시스템: 루틴 0x7cdc(표 0x7d34, 21레코드) — 레코드 = attr.w, dest.l(pf0 셀, 글리프의 우상단), 워드 k…(k=0 공백)
# → 타일 k=우상, k+1=우하, k+2=좌상, k+3=좌하 로 16×16 글자. 0xfffe 다음 세그먼트, 0xffff 끝. 문자 ROM 0x1c0~0x32f 가 일본어 쿼드 폰트.
# 게임 중 NPC/보스 대사(14~16)는 이 경로로 그려진다(16×16 타일맵 사본 X:0ab570/0ab7f0/0aba70 과 같은 문장).
QUAD_TABLE = 0x7D34
QUAD_RECORDS = {14: "QD:14", 15: "QD:15", 16: "QD:16"}
QUAD_TWIN = {"QD:14": "X:0ab570", "QD:15": "X:0ab7f0", "QD:16": "X:0aba70"}   # 같은 문장의 16×16 타일맵 레코드
_QROWS = {0x180: "ABCDEFGHIJKLMNOP", 0x1C0: "QRSTUVWXYZようこそとい", 0x200: "た所ですがの必要はありませんねな",
          0x240: "ご死ぬか&・！?←：.,", 0x280: "られ以上私計画を邪魔きに私自身お", 0x2C0: "相手しても下僕是非とさわロルス存", 0x300: "分遊げ‥、。！‼〝〞"}
QUAD_FONT_MAP = {base + 4 * i: c for base, row in _QROWS.items() for i, c in enumerate(row)}
QUAD_FONT_MAP.update({0x140 + 4 * i: str(i) for i in range(10)})
QUAD_REUSE = {"‥": 0x30C, "‼": 0x31C, "〝": 0x320, "〞": 0x324, "“": 0x320, "”": 0x324, "・": 0x254, "·": 0x254, "?": 0x25C, "!": 0x318, "：": 0x264}


def quad_record(img: bytes, idx: int) -> tuple[int, int, list[tuple[int, int, list[int]]]]:
    """(start, end, [(attr, dest, words)])"""
    import struct
    rec = struct.unpack_from(">I", img, QUAD_TABLE + 4 * idx)[0]
    o, segs = rec, []
    while True:
        attr = struct.unpack_from(">H", img, o)[0]
        dest = struct.unpack_from(">I", img, o + 2)[0]
        o += 6
        ws = []
        while True:
            w = struct.unpack_from(">H", img, o)[0]
            o += 2
            if w in (0xFFFE, 0xFFFF):
                break
            ws.append(w)
        segs.append((attr, dest, ws))
        if w == 0xFFFF:
            return rec, o, segs


def quad_split(tile16: list[list[int]]) -> list[list[list[int]]]:
    """16×16 → [우상, 우하, 좌상, 좌하] 8×8 (쿼드 프린터 순서 k, k+1, k+2, k+3)."""
    def sub(y0, x0):
        return [[tile16[y0 + y][x0 + x] for x in range(8)] for y in range(8)]
    return [sub(0, 8), sub(8, 8), sub(0, 0), sub(8, 0)]
