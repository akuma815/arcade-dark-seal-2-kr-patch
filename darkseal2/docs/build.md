# Dark Seal 2 (darkseal2) 한글 빌드 파이프라인

원장(SSOT) `workspace/text/translation/ds2_translation.json` → `build_translation.py` → `build/<name>/` (패치된 ROM 6개 + IPS + dat + report.json) → FBNeo `support/ips/darkseal2/<name>.dat` 자동 설치. 원본은 `extracted/`(읽기 전용)에서만 읽는다.

## 1. 단계

| 단계 | 스크립트 | 산출물 |
| --- | --- | --- |
| 원문 추출 | `workspace/scripts/extract_text.py` | `text/source/ds2_blocks.json` — 메시지 블록 27 + 하늘 스토리 1 + NPC 3 + 엔딩 2 = 33 레코드 |
| 글리프 전사 | `glyph_map.py sheet/fill/decode` | `font/mapping/ds2_glyph_map.json` (뱅크 0xa03~0xb4b + 0xdcf~0xe9b, 372 항목, `▣`=비글자) |
| 원장 생성 | `make_ledger.py` | `ds2_translation.json` (레코드별 layout.rows[i].span, 하늘은 panel_rows/text_row0) |
| 초벌 반영 | `apply_drafts.py drafts_v1.json` / `drafts_v2_extra.json` | 원장 status=draft, 셀 폭·문자 공급 검사 |
| 빌드 | `build_translation.py --name kr` | `build/kr/`, FBNeo 설치. 릴리즈는 `--name Korean --min-status approved --desc "영문설명／한글설명"`(구분자는 세로줄) |
| 배포 | `python common/scripts/make_dist.py darkseal2 --name Korean --version 1.0.3` | `dist/darkseal2_KR_v1.0.3_20261005.zip` (sha256 7b20e693…, 워프 방 배경 수정판). 폐기: v1.0(MAME 계열 캐릭터 선택 예외), v1.0.1(요새 컷신 첫 줄 의미불명), v1.0.2(워프 방 배경 깨짐 — 하늘 레코드 0행의 포인터 표를 0으로 덮음) |

## 2. 빌더가 하는 일 (`build_translation.py`)

1. 원본 왕복(프로그램 이미지 encode/decode, gfx2 DECO74 복호→16×16 디코드→인코드→암호화 동일) 확인.
2. **글리프 배정(2스타일)** — 2026-10-05 사용자 요청으로 단일 스타일에서 변경: A = 배경 2·본체 7(대사 상자·프롤로그·하늘 패널·엔딩 — 원본도 배경 2 또는 검정 위), B = 배경 0 투명·본체 7·외곽선 2(게임 화면 위에 직접 그리는 `line` 레코드: 석판 힌트·보스 대사). 같은 글자라도 두 스타일이면 타일 2개. 현재 A 253 + B 100 = 353 / 가용 371(쌍둥이 타일맵 X:0ab570/0ab7f0/0aba70 은 `ignored` — §3f, 0xdc2~0xdce 는 스태프롤 미사용으로 풀에 포함). 풀 = 폰트 뱅크 − 보존(미번역 레코드가 쓰는 타일 + 스태프롤 전용 0xe09~0xe10 + 재사용 문장부호) − 비글자(`▣`, 상자 채움 0xa88, 엔딩 채움). 현재 재사용 6·신규 262 / 가용 357.
3. 타일맵 재작성(레코드 kind: box=0xa88 채움, prologue/line=0 채움, ending=원 채움 타일, sky=패널 전부 0xa88 + 행 `text_row0`(=1)부터 가로 줄 + 하단 상자 줄 `ko_box_row`). mas12/13 **미러 2벌 모두** 기록.
4. **하늘 장면 코드 패치 4곳**(`ds2lib.SKY_SCENE_PATCHES`, `--sky-crawl` 로 생략 가능) — §3.
5. Expected Write: 허용 범위 밖 바이트 변경 시 실패(`patchutil.check_allowed`).
6. IPS/dat 생성, report.json(`scripts`, `code_patches`, `roms`, `glyph_alloc`, `untranslated`).

## 3. 하늘 스토리 장면 정지 패치 (어트랙트 「古老曰く…」)

원작은 세로쓰기 텍스트 레이어가 오른쪽→왼쪽으로 흘러 들어오는 크롤이라 가로 패널(열 0~19)이 잘려 지나간다. 루틴 0x1caa~0x1dfe(클론 프로그램 `jb-01-3.3d`/`jb-00-3.3a`) 디스어셈블로 확정:

| 주소 | 원본 | 패치 | 의미 |
| --- | --- | --- | --- |
| 0x1cfa | `move.l #$01400000,$fdc17c` | `#$0` | 텍스트 레이어 X(16.16 고정소수) 시작 0x140 → 0 |
| 0x1d8e | `subi.l #$4000,$fdc17c` | `#$0` | 매 프레임 −0.25px → 정지 (루프 종료는 0xfdc16c 의 0x3ff 랩이 결정하므로 길이 1280프레임 유지) |
| 0x1dbe | `move.w #$80,d7` (+`jsr $cc8` 프레임 대기) | `#$200` | 정지 후 유지 128 → 512 프레임 (읽기 시간, 총 ≈30초) |
| 0x1d04 | `move.w #$1fc,$fdc180` | `#$1f8` | 텍스트 레이어 Y 4px 내림 — 블록 행 r 의 셀 위 = 16r−20(캡처 실측) 이므로 행 1~15 가 y0~240 에 정확히 맞음 |

- 스크롤 변수: 0xfdc17c→0x310002(매 프레임 0x102a0), Y = 0xfdc180 + 0xfdc134. 0xfdc14a(카메라) 경유 아님 — 이 장면은 직접 기록.
- 부작용: 뒤 어트랙트 장면이 384프레임 늦어짐(캡처 프레임 번호 기준). 하단 상자 행(블록 행 28)은 이 장면에선 화면 밖(원작과 동일).
- 증거: [evidence/kr_sky_static_3400.png](evidence/kr_sky_static_3400.png), [evidence/kr_attract_sky_static_sheet.png](evidence/kr_attract_sky_static_sheet.png) (프롤로그·컷신·하늘 패널 3400/4900·타이틀·프로필).

## 3b. 프로필 화면 (8×8 타일맵 + 문자 ROM) — 사용자 요청 2026-10-04

- 구조: 어트랙트 루틴 0x3c7a(5인)·0x3dc4(3인)가 로더 0x1045a 로 **40×32 8×8 타일맵 블록**(포인터 배열 0xb5288, 블록 4~11, 부모 mas12/13)을 pf0(0x200000, 행 128B)에 복사. 워드 = pal<<12 | 타일(문자 ROM 직접 인덱스). 글자 타일 0xeb8~0xf79(라벨·가나·숫자, 본체 1·그림자 2), 탁점은 **위 행의 별도 타일**(f03/f2e=゛, f00=゜, edd=틀+゛). 전사표 `font/mapping/ds2_profile_font_map.json`, 추출 `extract_profile.py` → `text/source/ds2_profile_blocks.json`(원장 kind=profile 8항목).
- 한글 글리프: 문자 ROM(`jb-04.10d`/`jb-05.12d`, DECO 74)의 **빈 타일 0x928~0xbff(728개)** 에 Galmuri7 8×8 을 본체 1·그림자 2 로 기록(`ds2lib.hangul8_tile`). 숫자·괄호·〝〞·: 는 원본 타일 재사용, `.`/`,` 는 수제. 현재 신규 298.
- 레이아웃: 스탯 행(2,4,6,8,10,12,14; P9~11 은 15)은 라벨 열부터 열 38 까지 교체(`ko_cells`), 본문은 `ko_body` 단락을 38셀로 줄바꿈해 **짝수 행 18~28(6줄, 행 간격 2 고정)** — 6줄 초과면 apply_drafts 가 오류(문장 축약). 홀수 행의 탁점은 지움. 단위 inch/lb → cm/kg 환산.
- P4(카를)만 ASCII 프린터 0x4c28(표 0x4c92, 인덱스 0x8c → 레코드 0x7ca0)이 "Morning Star" 를 행 14 열 22 에 덧그림(블록의 "Mornig" 오타 보정) → 레코드 텍스트 첫 2바이트를 `ff ff` 로(`PROFILE_OVERLAY_PATCH`).
- 증거: [evidence/kr_profile_cycle1_sheet.png](evidence/kr_profile_cycle1_sheet.png)(5인, 100프레임 간격), [evidence/kr_profile_jade.png](evidence/kr_profile_jade.png), 폰트 시트 [evidence/profile_font_0ec0_0f7f.png](evidence/profile_font_0ec0_0f7f.png).

## 3c. 랭킹 화면(계급명·직업 라벨·제목) — 사용자 요청 2026-10-04

- 계급명: 루틴 0x2410 이 플레이어 구조(0xfdc034+8n, +3 = 계급 0~5)의 계급 인덱스로 표 0x251c 의 6바이트 ASCII("SQUIRE…KING")를 pf0 에 바이트=타일로 복사. 패치: 복사 루프 0x2470 `move.b (a1)+,d1 / move.w d1,(a2)+` → `move.w (a1)+,(a2)+ / nop`, 6×6 워드 문자열을 빈 공간 0x3ff00 에, 표 재지정(`ds2lib.RANK_*`). 원장 `RK:0`(kind=rank).
- 제목 "LEGENDARY HEROES"·직업 라벨 5개는 ASCII 프린터 0x4c28 레코드(0x3b/0x3c). 타일 = attr|바이트 이므로 attr 0x0900 으로 **0x929~0x9fe 에 따로 배정한 한글 글리프**를 바이트 하나로 지정. 새 레코드를 0x3fd00~ 에 쓰고 표 0x4c92 재지정, 세그먼트별 원문 중앙 정렬. 원장 `AS:3b`·`AS:3c`(kind=ascii, `layout.segments`).
- **MAME 호환(v1.0.1, 2026-10-05)**: 새 레코드를 빈 공간에 이어 쓸 때 길이가 홀수면 다음 레코드가 홀수 주소에 놓여, 68000 어드레스 에러(프린터 0x4c6a 의 `movea.l (a0)+`)가 난다. FBNeo 의 CPU 코어는 묵인해 못 잡았고 EKMAME(MAME 계열) 제보로 발견 — 캐릭터 선택 화면에서 EXC 화면. 레코드 시작뿐 아니라 **레코드 안의 세그먼트 경계**도 짝수여야 한다(원본은 "ELF"+0 처럼 홀수 문자열에 0 패딩). 빌더가 홀수 길이 세그먼트에 0 을 덧붙이고, 레코드 시작·세그먼트·dest 홀짝을 모두 검사한다. EKMAME 에서 autoboot Lua(코인·스타트 자동 입력, 스냅샷)로 캐릭터 선택·어트랙트 재검증 — `EKMAME/autoboot_select.lua`, `autoboot_attract.lua`. **교훈: 68000 데이터/코드 패치는 항상 워드 정렬, 검증은 MAME 계열에서도 한 번.**
- 글리프 영역 분담: 프로필·계급 = 0xbff 부터 내려감, ASCII 레코드 = 0x929 부터 올라감(0x928 = 공백). 합계 ≤ 728.
- 증거: [evidence/kr_ranking_screen.png](evidence/kr_ranking_screen.png) (어트랙트 데모 뒤 약 9200프레임).

## 3d. 캐릭터 선택 화면·게임 중 ASCII 메시지 — 사용자 요청 2026-10-04

- 설명문 5줄(びょうきにたいせいがある 등)은 **워드 레코드**(루틴 0xa5e0 부근, 표 0xa614 → 레코드 0xa61c: `[dest.l][워드…][fffe 다음][ffff 끝]`, 워드 = pal|8×8 가나 타일 0x0ee~0x11e, 탁점은 윗행 세그먼트). 한글은 같은 자리(190B)에 제자리 재기록, 탁점 세그먼트 제거. 원장 `WR:a61c`(kind=wordrec), 가나 부분 전사 `font/mapping/ds2_kana8_map.json`.
- "SELECT YOUR CHARACTER"/"TIME" 은 ASCII 레코드 0x3d(`AS:3d`), 상태이상 메시지 POISON…DISEASE 는 0x08~0x13(`AS:08`~`AS:13`, pal 5 유지) — §3c 방식.
- 자동 QA: `fbneo_dump.py --press "400:P1 Coin,470:P1 Start"`(Lua `joypad.set({["P1 Coin"]=true})`, 플레이어 인덱스 없음)로 게임 시작까지 자동 진행. 증거: [evidence/kr_character_select.png](evidence/kr_character_select.png).

## 3e. 누락 메시지 발견과 스태프롤 보존 — 2026-10-04 (사용자 플레이 QA 보고: 부유요새 진입 메시지 깨짐)

- 원인: 메시지 블록(0xa4950, 20열)을 0xa8800 까지만 레코드화해 그 뒤의 **게임 중 메시지 9건**(석판 힌트 0xaab98, 보스 대사 0xaadf0~0xac470)이 누락됐고, 그 가나 타일이 한글로 재배정돼 깨짐. 블록 전 범위(0xa4950~0xb0000)를 **블록 기준 20열 정렬**로 재스캔해 찾음(처음 0xa8800 기준으로 스캔하면 4셀 어긋남 — 주의).
- 추가 전사: 한자 타일 0xdc2~0xe04 44자(`ds2_glyph_map.json`), `extract_text.py` EXTRA_REGIONS 9건(kind=line) + **credits(0xac600, 224행, kind=credits, untranslated)** — 스태프롤이 쓰는 167타일(가나 포함)이 보존 집합에 들어가게 함. 이전 빌드는 스태프롤 가나가 깨졌을 가능성이 큼(미확인).
- 결과: 16×16 글리프 신규 291 / 가용 361, 보존 185. 오프라인 렌더(패치 ROM 직접 디코드) [work/offline_render_newmsgs.png] 로 석판 메시지·보스 대사·스태프롤 행 확인. 교훈: **같은 블록은 끝까지 열거하고, 번역하지 않는 소비자(스태프롤)도 레코드로 등록해 타일을 보존한다.**

## 3f. 게임 중 NPC/보스 대사 = 쿼드(2×2 8×8) 시스템 — 2026-10-05 (사용자 보고: 부유성 보스 대사 일본어)

- 원인: 게임 중 NPC/보스 대사는 16×16 타일맵(gfx2)이 아니라 **문자 ROM의 쿼드 폰트**(0x1c0~0x32f, 2×2 8×8 = 16×16 글자)로 pf0 에 그려진다. 루틴 0x7cdc, 표 0x7d34(21레코드), 레코드 = attr.w, dest.l(글리프 우상단 셀), 워드 k(타일 k=우상, k+1=우하, k+2=좌상, k+3=좌하; 0=공백), fffe 다음 세그먼트, ffff 끝. 14~16 = NPC 환영/보스 2대사(16×16 타일맵 X:0ab570/0ab7f0/0aba70 과 같은 문장 — 그쪽은 사용처 미확인, 둘 다 번역 유지). 12/18/19/20 = GAME OVER / TO BE CONTINUED / STAFF / DATA EAST(영문 유지).
- 패치: 한글 16×16(Galmuri11, **본체 7(흰색)·외곽선 2** — 원본 가나 쿼드와 동일. 영숫자 쿼드/HUD 폰트는 1/2 라 1 을 쓰면 녹색으로 나옴)을 8×8 네 장으로 쪼개 빈 타일 0x928~0xbff 의 연속 4칸에 배정(`quad_split`), 레코드 제자리 재기록. **원본 세그먼트 길이만큼 공백(0)으로 채워** 이전 대사를 지운다(안 하면 이전 줄이 남음). 레코드 길이 초과 시 문장 축약(QD:15 3행, QD:16 1행 줄임). 원장 `QD:14~16`(kind=quad), 쌍둥이 X: 레코드와 문장 동기.
- 발견 방법: 세이브(F10) 상태를 F9 로 불러 30프레임 간격 레이어 덤프 → 대사 표시 중 pf0 만 변함(244셀) → 2×2 패턴(k+2,k / k+3,k+1) → ROM 에서 워드열 검색(0x7f16).
- 상태 `ignored`(번역도 보존도 안 함): 쿼드로 그려지는 세 문장의 16×16 타일맵 사본. 어디선가 깨진 글자가 보이면 이 세 레코드를 의심할 것.
- 증거: [evidence/kr_boss_dialog_quad.png](evidence/kr_boss_dialog_quad.png), 2스타일 오프라인 렌더 [evidence/kr_twostyle_offline_render.png](evidence/kr_twostyle_offline_render.png), 쿼드 폰트 시트 [evidence/charrom_quad_font.png](evidence/charrom_quad_font.png). 8×8 예산: 프로필/ASCII 344 + 쿼드 63×4 = 596 / 728.

## 3g. 하늘 스토리 — 검은 패널 제거, 투명 글자 + 배경 스크롤 유지 (2026-10-05 사용자 결정)

- 정지 패치(§3)는 그대로이고(글자 레이어 X만 고정; 구름 pf1·하늘 pf4는 원본대로 흐름), 패널 채움(0xa88)을 없애고 하늘 본문을 투명 스타일(B)로 바꿈. 하단 상자 줄(행 28, 검은 상자 위)만 배경 스타일(A) 유지(`SKY_BOX_ROW0`).
- 예산: 하늘 89자가 B 로 가면 385/371 이라, 사용자와 문안을 손질(출처 줄 축약·평정하여도→잠재워도·않으리→아니하리·군세로써→군세로·무엇으로→어찌·역시→다시·소란이→난리가·물어 이르길→물어보길·답하여 이르길→답하길) → **362/371**. 2안(프롤로그도 투명)은 397 로 오히려 증가(프롤로그 62자 중 44자가 상자와 공유).
- 함정: 투명 스타일 재사용 표가 하늘 원문의 **세로쓰기용 「」 타일**(a03/a2c, ┐┘ 모양)을 집어 와 괄호가 어긋남 → `VERTICAL_ONLY` 로 재사용 금지, Galmuri11 로 새로 그림.
- 증거: [evidence/kr_sky_transparent_3400.png](evidence/kr_sky_transparent_3400.png).

## 3h. 요새 접근 컷신 첫 대사 = 하늘 레코드의 상자 줄 (2026-10-05 EKMAME 제보: "의미불명 한글")

- 증상: 부유요새 접근 컷신(제이드 「何かしら、あれは？」→ 이후 대사들)의 **첫 줄만** "재데크범호록또죽니" 같은 의미불명 한글. 나머지 줄(「놈들의 부유요새다‥‥‼」 등 메시지 블록 레코드)은 정상.
- 원인: 그 줄은 별도 레코드가 아니라 **하늘 스토리 레코드 X:0a39d8 의 행 28(0xa3e38) = 하단 상자 줄**과 같은 타일맵 행을 공유한다. §3g 에서 `panel_rows` 를 [0,32] 로 넓힌 뒤 빌더의 "패널 밖 span 행" 조건이 빈 집합이 되어 `ko_box_row`(「뭘까, 저건?」)가 **한 번도 기록되지 않았고**, 원문 가나 타일 번호가 그대로 남은 채 그 타일들이 한글 글리프로 재배정되어 의미불명 한글이 됐다. 하늘 장면에서는 행 28 이 화면 밖이라 QA 에 안 잡혔다.
- 수정: `build_translation.py` 상자 줄 선택을 `행 ≥ SKY_BOX_ROW0(27)` 기준으로 고정 + 못 찾으면 빌드 실패. 행 28 = `▣▣▣「뭘까,▣저건?」▣…`(A 스타일, 글리프는 이미 예산에 포함돼 있어 362/371 변동 없음).
- 진단 경로(재사용 가치): EKMAME 세이브(`-state` 는 Lua 와 같이 쓰면 안 올라옴 → Lua 안에서 `machine:load("z")`) → `autoboot_state.lua` 가 스냅샷 + pf0~pf3 RAM 덤프 → 덤프의 타일 번호를 `report.json glyph_alloc`(한글)·`ds2_glyph_map.json`(원문)으로 되돌려 "「何かしら" 복원 → ROM 에서 행 검색 → 0xa3e38 = 하늘 레코드 안. 쌍둥이 레코드(X:0ab570 등)·쿼드·렌더링 차이는 모두 무관했다(쿼드 타일표를 두 에뮬레이터에 그려 비교, `EKMAME/snap_sheet/`).
- 부수 발견: 컷신 중 pf3 상단 5행에 ROM 0xb1e08 의 연속 타일 청크(0xdca~0xe91, 팔레트 1)가 깔린다 — 원본도 한자·가나판 그대로이고 화면 밖/장식이라 방치(스냅샷 33장에서 안 보임). 비슷한 연속 타일 영역 18곳 목록은 세션 로그(25) 참조.
- 사용자 확인(2026-10-05): v1.0.2 에서 「뭘까? 저건」 정상. 같은 세이브의 '워프 전환 직후 배경 깨짐'은 처음엔 패치 무관으로 봤으나 **오판** — §3i.
- 주의: 세이브 상태는 그 줄이 이미 VRAM 에 그려진 뒤라 ROM 을 고쳐도 로드 직후 화면은 그대로다(검증은 그 전 시점에서 다시 진입해야 함).

## 3i. 워프 방 배경 깨짐 = 하늘 레코드 "0행"이 청크 포인터 표 (2026-10-05, v1.0.3)

- 증상: 마법진 워프(모래 방·하늘 광선) 장면의 바닥/배경이 체크무늬 잡음. EKMAME 에서는 pf2(0x208000)에 ROM 0x000~ 바이트(벡터표)가 타일로 복사된 모습, FBNeo 에서는 다른 잡음. 처음엔 "ROM 미수정 영역의 복사 = 패치 무관"으로 오판했으나, **원본 ROM 으로 같은 FBNeo 세이브를 불러오니 멀쩡**(모래 바닥·계단) → 패치 원인.
- 분리: IPS 를 프로그램/데이터(mas12·13)/그래픽으로 나눠 세이브를 불러 비교 → 데이터만 깨짐 → mas12/13 변경 범위를 4구간으로 나눠 다시 비교 → **하늘 레코드 구간(0xa3000~0xa4950)** 만 깨짐.
- 원인: 추출기의 하늘 레코드 X:0a39d8 은 33행인데 **0행(0xa39d8~0xa3a00)은 텍스트가 아니라 청크 포인터 표의 끝 10개**(`000a e400 000a e680 …`; 표 전체 0xa38c8~0xa3a00, 78개). 실제 세로 텍스트는 1행(0xa3a00, 조사 노트의 0xa39fe)부터. §3g 의 투명화가 `panel_rows` 0~26 을 통째로 0 으로 덮어 포인터 0xae400/0xaee00/0xafa80 등이 0 이 됐고, 그 포인터를 쓰는 워프 방 배경 청크 복사가 ROM 0번지에서 읽었다(MAME 에서 벡터표 잡음으로 보인 이유). 포인터 하위 워드(e400·ee00·fa80)가 글자 타일 번호처럼 보여 "글자 칸만 지우기"로도 2개가 지워졌음 — **행 번호로 0행을 제외**해야 했다.
- 수정: `build_translation.py` 하늘 처리에서 `text_row0(1) ≤ r < SKY_BOX_ROW0` 행의 글자 타일 칸만 0 으로. 포인터 표 0xa38c8~0xa3a00 이 원본과 바이트 일치함을 확인. FBNeo(세이브 로드, 원본과 화면 차이 1.9/255)·EKMAME(x.sta 스냅샷 40장) 모두 정상.
- 교훈: (1) "레코드 = 20열 × N행" 가정으로 잡은 범위의 **첫/끝 행이 다른 데이터일 수 있다** — 글자 타일이 없는 행을 레코드에 넣지 말 것(추출기 EXTRA_REGIONS 의 sky base 는 0xa39d8 그대로 두되 빌더가 0행을 보호). (2) "변경하지 않은 영역이 복사됐다"는 패치 무관의 증거가 아니다 — 복사의 **포인터**가 변경 영역에 있을 수 있다. 반드시 원본 ROM + 같은 세이브로 대조할 것. (3) 세이브 로드 + IPS 부분 적용(프로그램/데이터/그래픽, 다시 주소 구간) 이분 탐색은 15초/회로 싸고 결정적이다.

## 4. QA 상태 (2026-10-04)

| 화면 | 방법 | 결과 |
| --- | --- | --- |
| 프롤로그 3 레코드, 컷신 상자 | 어트랙트 캡처 1300/2700 | PASS |
| 하늘 스토리 15줄 | 캡처 3400/4900 (+RAM 0xfdc17c=0, 0xfdc180=0x1f8); 2026-10-05 투명 글자판 3300~4900 | PASS (정지·전부 표시·배경 스크롤) |
| 게임 중 대사 상자 24, NPC 3, 엔딩 2 | 사용자 플레이 QA(`cheat_qa.lua`, 세이브 로드) | PASS — 사용자 최종 승인 2026-10-05 |
| 프로필 화면 8인(타이틀 뒤) | 1주기 5인 캡처 5800~7800, 2주기 3인 15200~16000 | PASS(한글·팔레트·행 간격) — [evidence/kr_profile_cycle2_sheet.png](evidence/kr_profile_cycle2_sheet.png), [evidence/kr_profile_wizards.png](evidence/kr_profile_wizards.png) |
| 랭킹 화면(제목·직업·계급) | 캡처 9200 | PASS |
| 캐릭터 선택(제목·시간·설명 5줄) | 코인/스타트 자동 입력 캡처 800 | PASS |
| 상태이상 메시지 6종×2P | 사용자 플레이 QA | PASS(사용자 최종 승인 2026-10-05) |
| 보스/NPC 쿼드 대사 3건 | 세이브 로드 캡처 | PASS(한글·이전 줄 지움) |
| 요새 접근 컷신 첫 줄(하늘 상자 줄 행 28) | ROM 행 디코드 + 사용자 EKMAME 재진입 | PASS(v1.0.2, 사용자 확인) |
| 워프 방 배경(마법진·하늘 광선) | FBNeo/EKMAME 세이브 로드, 원본 대조 + 사용자 플레이 | PASS(v1.0.3, 사용자 확인) |
| 스태프롤 | — | 일본어 유지(1편과 동일 방침 가정, 미확인) |

## 5. 재현 명령

```powershell
python darkseal2\workspace\scripts\apply_drafts.py darkseal2\workspace\text\translation\drafts_v1.json
python darkseal2\workspace\scripts\apply_drafts.py darkseal2\workspace\text\translation\drafts_v2_extra.json
python darkseal2\workspace\scripts\build_translation.py --name kr
python common\scripts\fbneo_dump.py darkseal2 --frames 1300 2700 3400 4900 --range fdc100:100 --ips kr --tag qa
python common\scripts\fbneo_play.py darkseal2 --ips kr --lua darkseal2\workspace\tests\cheat_qa.lua
```
