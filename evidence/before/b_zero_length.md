# b. length 0: 대조군

- 기준 커밋: `e77e5cf` (로컬 main. README만 다르고 코드는 `origin/main` `7e41b5c`와 같음, 소스 수정 없이 실행) · 실행 환경: Ubuntu (WSL2), Python 3.12.3
- 수집 스크립트: [`collect.py`](collect.py) · 원자료: [`raw.json`](raw.json) (`"b"` 키)

## 입력
`{"payload":"hello","length":0}` → `POST /heartbeat` (프록시 경유, 세션 `attacker-b`), 세 모드 각각

## 실행 명령
```bash
python3 evidence/before/collect.py    # 사례마다 타깃(해당 모드)+프록시를 새로 띄우고 일반 종료로 정리
```

## 출력
| 모드 | 단계 | 경로 | status | 응답 길이 | 진짜 비밀 | 응답 헤더(X-) | 응답 본문(앞 60자) |
|---|---|---|---|---|---|---|---|
| unpatched | b: hello / length 0 | proxy:8080 | 200 | 0 | 0 | - | `` |
| patched | b: hello / length 0 | proxy:8080 | 200 | 0 | 0 | - | `` |
| honeypatched | b: hello / length 0 | proxy:8080 | 200 | 0 | 0 | - | `` |

## 관찰
1. 세 모드 모두 200 · 0바이트 · 비밀 0건. `memory[:0]`은 빈 값이라 노출 없음.
2. fork 없음, `attacker.jsonl` 기록 없음(`over = -5`). 위반이 아니므로 기록되지 않는 것이 맞다.
3. a(음수)와 대비하면 문제는 '0 이하'가 아니라 **음수**에서만 생긴다는 것을 보여 주는 대조군.

## 로그 발췌 (단계별 증가분, 시각 `t` 제외)

**[unpatched] b: hello / length 0**

- 요청: `POST /heartbeat` · `X-Session-Id: attacker-b` · proxy:8080 · 본문 `{"payload": "hello", "length": 0}`
- 응답 본문 전체: `''`
- defender.jsonl:
  ```json
  {"event": "route", "session": "attacker-b", "to": "target", "status": 200}
  ```
- attacker.jsonl:
  - (기록 없음)

**[patched] b: hello / length 0**

- 요청: `POST /heartbeat` · `X-Session-Id: attacker-b` · proxy:8080 · 본문 `{"payload": "hello", "length": 0}`
- 응답 본문 전체: `''`
- defender.jsonl:
  ```json
  {"event": "route", "session": "attacker-b", "to": "target", "status": 200}
  ```
- attacker.jsonl:
  - (기록 없음)

**[honeypatched] b: hello / length 0**

- 요청: `POST /heartbeat` · `X-Session-Id: attacker-b` · proxy:8080 · 본문 `{"payload": "hello", "length": 0}`
- 응답 본문 전체: `''`
- defender.jsonl:
  ```json
  {"event": "route", "session": "attacker-b", "to": "target", "status": 200}
  ```
- attacker.jsonl:
  - (기록 없음)
