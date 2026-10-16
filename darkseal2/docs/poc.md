# Dark Seal 2 — PoC 기록

## PoC-1: 프롤로그 첫 줄 한글 그림 글자 (2026-10-04) — **PASS**

### 증명하려던 것
1. DECO 74 역변환(암호화)과 16×16 타일 인코더가 원본과 바이트 동일하게 왕복한다 (jb-04/05, mas00/01, mas02/03 전부).
2. gfx2 글리프 타일을 한글(Galmuri11 11×11 + 외곽선, 본체 7·외곽 2)로 바꾸고 mas12/13 타일맵 셀을 재작성하면 코드 수정 없이 화면에 한글이 나온다.
3. 부모 zip(`wizdfire.zip`) ROM 4개(mas02/03/12/13)의 IPS 가 darkseal2 실행 시 적용된다.

### 방법
- 형식 라이브러리 [workspace/scripts/ds2lib.py](../workspace/scripts/ds2lib.py), 빌더 [build_poc.py](../workspace/scripts/build_poc.py), 공용 [common/scripts/deco74.py](../../common/scripts/deco74.py)(decrypt/encrypt/16×16 decode·encode)·[patchutil.py](../../common/scripts/patchutil.py)
- 행 0 의 원본 글리프 타일 9개(0xa59 0xa5a 0xa5b 0xa5c 0xa55 0xa5d 0xa5e 0xa60 0xa61)를 한글 9자로 덮어쓰고(PoC 한정 — 같은 글자가 쓰인 다른 문장도 바뀜), 블록 0xa4950 행 0 의 2~13열을 재작성(미러 2벌). Expected Write 통과.
- 실행: `python common\scripts\fbneo_dump.py darkseal2 --frames 1300 --range 208000:1000 --ips poc --tag poc`

### 결과
- 화면: [evidence/poc1_screenshot.png](evidence/poc1_screenshot.png) — 흰 한글 + 검은 외곽선, 타자기 효과도 그대로.
- 레이어 2 덤프: 행 2, 열 2~13 = `갈리아력 ␣ 삼오오년 ␣ 칠월` 의 타일 순서와 정확히 일치.
- 첫 시도에서 2셀 밀림 → 블록 행이 32열이 아니라 **20열(시작 0xa4950)** 임을 실측해 교정. survey §4 갱신.

### 한계·주의
- 글리프 뱅크 0x9c0~0xb3f 는 빈 슬롯이 없다. 본 번역에서는 (a) 일본어 글리프 전부를 한글 글리프로 치환(수요 ≤ 384 이면 가능), (b) 다른 빈/미사용 타일 영역 확보 — 중 하나를 수요 산출 후 결정.
- 메시지 블록을 청크 테이블 어디서 참조하는지는 미확인(0x8fc28 테이블엔 없음). 같은 위치·같은 크기로 덮어쓰는 한 문제 없다.
- 숫자·문장부호 16×16 글리프는 시트에 없어 별도 제작 필요(PoC 는 한글만).
