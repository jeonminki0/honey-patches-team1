# CLAUDE.md

이 저장소는 보안 논문 *From Patches to Honey-Patches* (Araujo et al., ACM CCS 2014)를 Python으로 축소 구현한
5인 팀 과제(Mini RedHerring)다. 프로젝트 설명은 [README.md](README.md), 팀 작업 규칙은 [CONTRIBUTING.md](CONTRIBUTING.md)에 있다.

## 실행

```bash
python demo/run_demo.py      # 3모드(unpatched/patched/honeypatched) × 고정 사례 3종 실행 → 마지막 줄 "15/15 통과"가 정상
python demo/run_extra.py     # 13주차 추가 사례(반례 탐색) 실행 → results/extra_results.md
```

- 포트: 8080(프록시), 9000(타깃), 9101·9102(미끼) — `honeypatch/config.py`에서 변경. 미끼는 프록시(`proxy/pool.py`)가 띄운다.
- 산출물: `results/compare.md`(비교표·PASS/FAIL), `results/raw_results.json`, `results/extra_results.md`(추가 사례 결과), `logs/defender.jsonl`(방어자 내부 로그, `run_demo.py` 실행 때마다 새로 생성), `logs/attacker.jsonl`(공격자 행위 로그, 초기화되지 않고 누적됨)
- 별도 테스트 프레임워크 없음. 고정 사례는 `run_demo.py`의 `judge()`가, 추가 사례는 `demo/extra_cases/*.json`의 `expect`와 `run_extra.py`가 판정한다.

## 구조

| 경로 | 역할 | 논문 대응 |
|---|---|---|
| `honeypatch/config.py` | 포트, 시드 사용자(진짜 비밀), `real_secrets()` | — |
| `honeypatch/hp.py` | `hp_init` / `hp_fork` / `hp_skip` | §3, Listing 2·3 |
| `honeypatch/redact.py` | 같은 길이·형식, 모든 글자가 원본과 다른 가짜 값으로 비밀 치환 | §4.1 |
| `server/app.py` | Heartbleed 구조를 흉내 낸 `/heartbeat`, `GET /files/<이름>`, `--mode`·`--role`, 미끼용 `/__hp/restore` | Listing 1·2 |
| `proxy/proxy.py` | 리버스 프록시, 세션 고정(`PINNED`), `X-HP-Forked` 시 미끼로 재전송, 세션 타임아웃, `dlog()`(방어자 로그)·`alog()`(공격자 로그) | §3 Reverse Proxy |
| `proxy/pool.py` | 미끼 풀: 미끼 프로세스 기동·`acquire()`·`release()`(destroy → clone → start) | §3 LXC Controller |
| `proxy/decoy_launcher.py` | 미끼 감싸기: 미끼(`server/app.py`)를 자식으로 띄우고, 부모(프록시) 종료 시 미끼 정리 (C7) | — |
| `data/`, `decoy_template/` | 타깃의 진짜 파일 / 미끼의 가짜 파일(허니파일) | — |
| `demo/fixed_cases.json` | 11주차 고정 검증 사례 3종 (normal / violation / boundary) | — |
| `demo/run_demo.py` | 서버·프록시 기동, 고정 사례 실행, 비교표·판정 | — |
| `demo/run_extra.py` | 추가 사례 실행기. 사례×모드마다 새로 기동, 기대/실제 대조, FAIL을 반례 후보로 정리 | — |
| `demo/extra_cases/` | 담당별 추가 사례(`*.json`)와 형식 설명(`README.md`) | — |
| `demo/client.py` | 수동 요청 CLI (`send()`는 run_demo에서도 사용) | — |
| `docs/counterexamples.md` | 반례 목록 C1~ (입력, 실행 전 기대, 실제, 분류, 근거, 처리) | — |
| `evidence/before/`, `evidence/after/` | 반례의 수정 전·후 증거 (같은 입력) | — |
| `tests/decoy_pool/` | 미끼 풀 단위 확인 스크립트 (release, 타임아웃, 허니파일) | — |
| `tests/decoy_pool/check_orphan.py` | 프록시 강제 종료 후 미끼 잔류 확인 (C7) | — |
| `logs/attacker.jsonl` | 공격자 행위 로그 (미끼로 간 요청·위반 입력·형식 오류 요청, 실행 시 생성) | — |

허니패치 흐름: 클라이언트 → 프록시 → 타깃 `/heartbeat`에서 `length > len(payload)` 탐지 → `hp_fork()`(상태 직렬화 + 공격자 외 비밀 redaction → 프록시 `/__hp/fork`) → 프록시가 미끼 acquire·restore·세션 고정 → 타깃은 `X-HP-Forked: 1`만 반환 → 프록시가 같은 요청을 미끼로 재전송 → 미끼에서 `hp_skip()`이 거부를 건너뛰고 가짜 비밀이 담긴 응답. fork 실패 시 타깃이 400으로 거부(일반 패치와 동일).

## 반드시 지킬 규칙

1. **Python 3.8 이상, 표준 라이브러리만 사용한다.** 외부 패키지(pip 설치, requirements 추가 등)는 금지. 3.9+ 전용 문법·API(예: `dict | dict`, `str.removeprefix`, `list[int]` 같은 내장 제네릭 타입 힌트, `match`)를 쓰지 않는다.
2. **경로는 저장소 기준 상대 경로만 사용한다** (`os.path` / `pathlib`). 기존 코드처럼 `os.path.dirname(__file__)` 기준으로 계산한다. `/home/...`, `C:\...` 같은 개인 PC 절대 경로를 하드코딩하지 않는다.
3. **`demo/fixed_cases.json`의 고정 검증 사례 3종은 입력(`session`, `request`)과 기대 결과(`expected`)를 절대 수정하지 않는다.** 사례 추가는 `demo/extra_cases/`에 하고, 기대 결과는 실행 전에 적는다.
4. **기대 결과와 다르게 나와도 결과에 맞춰 판정 코드(`run_demo.py`의 `judge()`)나 기대값을 바꾸지 않는다.** 실패하면 원인을 분석해 (입력, 실행 명령, 실제 출력, 원인 추정, 근거)를 보고한다. 수정은 원인이 된 구현 쪽에서 한다.
5. **공격자가 받는 응답과 방어자 내부 로그(`logs/defender.jsonl`)를 섞지 않는다.**
   - fork 여부, 미끼 포트, 라우팅 같은 방어자 정보는 `dlog()`로만 기록하고 응답 본문·헤더에 넣지 않는다.
   - 내부 헤더(`X-HP-*`)는 프록시가 공격자에게 돌려주기 전에 제거되어야 한다 (`proxy.py`의 `_reply()`는 Content-Type만 통과시킨다).
   - 응답 내용(가짜 비밀 포함)을 판정 근거로 방어자 로그에 섞어 쓰지 않는다.
6. **한 번에 한 기능만 수정하고, 수정 후 반드시 `python demo/run_demo.py`와 `python demo/run_extra.py`를 실행해 결과를 확인한다.** `run_demo.py`는 통과 수(15/15)와 FAIL 항목을, `run_extra.py`는 통과 수(사례×모드 기준)와 남은 FAIL 목록을 그대로 보고한다. 실행하지 않았으면 실행하지 않았다고 말한다.
7. **원논문과 다르게 구현한 부분은 README.md의 "원논문과의 차이" 표에 행을 추가한다.** (README는 김태우 담당이므로 추가할 내용을 함께 알린다.)
8. **파일 담당을 지킨다.** 담당 외 파일을 고쳐야 하면 먼저 사용자에게 알리고 해당 담당자와 조율한다.

   | 담당 | 파일 |
   |---|---|
   | 전민기 | `server/app.py`, `honeypatch/hp.py` |
   | 김영석 | `proxy/proxy.py` |
   | 우지민 | `proxy/pool.py`, `proxy/decoy_launcher.py`, `data/`, `decoy_template/`, `tests/decoy_pool/`, `.github/`, `CLAUDE.md`, `CONTRIBUTING.md` |
   | 이현우 | `honeypatch/redact.py`, `honeypatch/config.py` (다른 사람은 설정값 추가만 가능, 추가했으면 PR에 명시) |
   | 김태우 | `demo/`, `README.md`, `docs/counterexamples.md` (취합. 각 반례 행은 그 반례 담당자가 작성) |
   | 각 반례 담당자 | `evidence/` (자기 반례의 수정 전·후 증거) |

   **브랜치는 Issue 하나에 하나**: 최신 main에서 만들고(`fix/…`, `case/…`, `docs/…`), PR 설명에 `Closes #번호`를 적고, merge 후 삭제한다.

## 기타 참고

- main에 직접 커밋·push하지 않는다. Issue별 브랜치에서 작업하고 PR로 합친다 (CONTRIBUTING.md §2–4).
- 커밋 머리말: `feat:` / `fix:` / `test:` / `docs:`.
- AI를 활용했다면 PR 설명에 무엇을 요청했고, 어떻게 확인했고, 무엇을 채택·수정했는지 한두 줄 적는다.
- `logs/`, `results/compare.md`, `results/raw_results.json`, `results/extra_results.md`, `__pycache__/`는 `.gitignore` 대상이다. 실행 결과 파일은 커밋하지 않고, 남길 결과는 `evidence/`에 정리해 커밋한다.
