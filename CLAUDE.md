# CLAUDE.md

이 저장소는 보안 논문 *From Patches to Honey-Patches* (Araujo et al., ACM CCS 2014)를 Python으로 축소 구현한
5인 팀 과제(Mini RedHerring)다. 프로젝트 설명은 [README.md](README.md), 팀 작업 규칙은 [CONTRIBUTING.md](CONTRIBUTING.md)에 있다.

## 실행

```bash
python demo/run_demo.py      # 3모드(unpatched/patched/honeypatched) × 고정 사례 3종 실행 → 마지막 줄 "15/15 통과"가 정상
```

- 포트: 8080(프록시), 9000(타깃), 9101·9102(미끼) — `honeypatch/config.py`에서 변경
- 산출물: `results/compare.md`(비교표·PASS/FAIL), `results/raw_results.json`, `logs/defender.jsonl`(방어자 내부 로그, 실행할 때마다 새로 생성)
- 별도 테스트 프레임워크 없음. `run_demo.py`의 `judge()`가 기대 결과 판정을 담당한다.

## 구조

| 경로 | 역할 | 논문 대응 |
|---|---|---|
| `honeypatch/config.py` | 포트, 시드 사용자(진짜 비밀), `real_secrets()` | — |
| `honeypatch/hp.py` | `hp_init` / `hp_fork` / `hp_skip` | §3, Listing 2·3 |
| `honeypatch/redact.py` | 같은 길이·형식, 모든 글자가 원본과 다른 가짜 값으로 비밀 치환 | §4.1 |
| `server/app.py` | Heartbleed 구조를 흉내 낸 `/heartbeat`, `--mode`·`--role`, 미끼용 `/__hp/restore` | Listing 1·2 |
| `proxy/proxy.py` | 리버스 프록시, 미끼 풀 acquire, 세션 고정(`PINNED`), `X-HP-Forked` 시 미끼로 재전송, `dlog()` | §3 Reverse Proxy / LXC Controller |
| `demo/fixed_cases.json` | 11주차 고정 검증 사례 3종 (normal / violation / boundary) | — |
| `demo/run_demo.py` | 서버·프록시 기동, 사례 실행, 비교표·판정 | — |
| `demo/client.py` | 수동 요청 CLI (`send()`는 run_demo에서도 사용) | — |

허니패치 흐름: 클라이언트 → 프록시 → 타깃 `/heartbeat`에서 `length > len(payload)` 탐지 → `hp_fork()`(상태 직렬화 + 공격자 외 비밀 redaction → 프록시 `/__hp/fork`) → 프록시가 미끼 acquire·restore·세션 고정 → 타깃은 `X-HP-Forked: 1`만 반환 → 프록시가 같은 요청을 미끼로 재전송 → 미끼에서 `hp_skip()`이 거부를 건너뛰고 가짜 비밀이 담긴 응답. fork 실패 시 타깃이 400으로 거부(일반 패치와 동일).

## 반드시 지킬 규칙

1. **Python 3.8 이상, 표준 라이브러리만 사용한다.** 외부 패키지(pip 설치, requirements 추가 등)는 금지. 3.9+ 전용 문법·API(예: `dict | dict`, `str.removeprefix`, `list[int]` 같은 내장 제네릭 타입 힌트, `match`)를 쓰지 않는다.
2. **경로는 저장소 기준 상대 경로만 사용한다** (`os.path` / `pathlib`). 기존 코드처럼 `os.path.dirname(__file__)` 기준으로 계산한다. `/home/...`, `C:\...` 같은 개인 PC 절대 경로를 하드코딩하지 않는다.
3. **`demo/fixed_cases.json`의 고정 검증 사례 3종은 입력(`session`, `request`)과 기대 결과(`expected`)를 절대 수정하지 않는다.** 사례 추가가 필요하면 별도 파일로 분리하고 먼저 팀원4·사용자와 상의한다.
4. **기대 결과와 다르게 나와도 결과에 맞춰 판정 코드(`run_demo.py`의 `judge()`)나 기대값을 바꾸지 않는다.** 실패하면 원인을 분석해 (입력, 실행 명령, 실제 출력, 원인 추정, 근거)를 보고한다. 수정은 원인이 된 구현 쪽에서 한다.
5. **공격자가 받는 응답과 방어자 내부 로그(`logs/defender.jsonl`)를 섞지 않는다.**
   - fork 여부, 미끼 포트, 라우팅 같은 방어자 정보는 `dlog()`로만 기록하고 응답 본문·헤더에 넣지 않는다.
   - 내부 헤더(`X-HP-*`)는 프록시가 공격자에게 돌려주기 전에 제거되어야 한다 (`proxy.py`의 `_reply()`는 Content-Type만 통과시킨다).
   - 응답 내용(가짜 비밀 포함)을 판정 근거로 방어자 로그에 섞어 쓰지 않는다.
6. **한 번에 한 기능만 수정하고, 수정 후 반드시 `python demo/run_demo.py`를 실행해 결과를 확인한다.** 실행 결과(통과 수, FAIL 항목)를 그대로 보고한다. 실행하지 않았으면 실행하지 않았다고 말한다.
7. **원논문과 다르게 구현한 부분은 README.md의 "원논문과의 차이" 표에 행을 추가한다.** (README는 팀원5 담당이므로 추가할 내용을 함께 알린다.)
8. **파일 담당을 지킨다.** 담당 외 파일을 고쳐야 하면 먼저 사용자에게 알리고 해당 담당자와 조율한다.

   | 담당 | 파일 | 브랜치 |
   |---|---|---|
   | 팀원1 | `server/app.py` | `feat/server` |
   | 팀원2 | `proxy/proxy.py` | `feat/proxy` |
   | 팀원3 | `honeypatch/` | `feat/honeypatch` |
   | 팀원4 | `demo/` | `feat/demo` |
   | 팀원5 | `README.md`, 보고서 | `docs/readme` |

## 기타 참고

- main에 직접 커밋·push하지 않는다. 담당 브랜치에서 작업하고 PR로 합친다 (CONTRIBUTING.md §2–4).
- 커밋 머리말: `feat:` / `fix:` / `test:` / `docs:`.
- AI를 활용했다면 PR 설명에 무엇을 요청했고, 어떻게 확인했고, 무엇을 채택·수정했는지 한두 줄 적는다.
- `logs/`, `results/raw_results.json`, `__pycache__/`는 `.gitignore` 대상이다. `results/compare.md`는 커밋된다.
