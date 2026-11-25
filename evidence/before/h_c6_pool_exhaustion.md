# h. C6: 공격 요청 하나가 미끼 하나를 차지해 미끼 풀이 고갈됨 (Issue #15)

- 기준 커밋: `22f7b9d` (main, 소스 수정 없이 실행) · 실행 환경: Ubuntu (WSL2), Python 3.12.3
- 사례: `demo/extra_cases/pool.json`의 `C6-pool-exhaustion` (기대 결과는 실행 전 작성)
- 이 반례는 원논문 한계로 분류하고 코드를 고치지 않으므로 `evidence/after/`는 만들지 않는다.

## 입력
허니패치 모드, 미끼 풀 크기 2(`config.DECOY_PORTS = [9101, 9102]`). 모두 프록시 경유 `POST /heartbeat`.
외부 `/__hp/fork`(C8)는 쓰지 않고 정상적인 공격 요청만 보낸다.

| 단계 | 세션 | 본문 | 의도 |
|---|---|---|---|
| 1 | `attacker-1` | `{"payload":"hi","length":64}` | 미끼 1 소모 |
| 2 | `attacker-2` | 같은 공격 | 미끼 2 소모 (풀이 빔) |
| 3 | `attacker-3` | 같은 공격 | 풀 고갈 상태의 공격 |
| 4 | `user-normal` | `{"payload":"hello","length":5}` | 정상 사용자 영향 확인 |

## 실행 명령
```bash
python3 demo/run_extra.py --case C6-pool-exhaustion    # 타깃(honeypatched)+프록시를 새로 띄우고 일반 종료로 정리
```

## 출력

| 단계 | 항목 | 기대(실행 전) | 실제 | 판정 |
|---|---|---|---|---|
| 1 attacker-1 | status / len / forks / route / leaks | 200 / 64 / 1 / decoy / 0 | 200 / 64 / 1 / decoy / 0 | PASS |
| 2 attacker-2 | status / len / forks / route / leaks | 200 / 64 / 1 / decoy / 0 | 200 / 64 / 1 / decoy / 0 | PASS |
| 3 attacker-3 | status / forks / route / leaks | 400 / 0 / target / 0 | 400 / 0 / target / 0 | PASS |
| 4 user-normal | status / body / route | 200 / `hello` / target | 200 / `hello` / target | PASS |

`run_extra.py` 판정: **1/1 통과** (항목 17개 모두 PASS). 3단계 응답 본문은 `bad heartbeat`(13바이트, attacker.jsonl의 `resp_len: 13`)이다.

`fork_fail`은 `run_extra.py`의 expect 항목에 없어(`forks`는 `fork_ok`만 셈) 아래 로그로 확인했다.

## 관찰
1. **기대한 대로 동작한다.** 1·2단계는 미끼로 기만되고(진짜 비밀 0), 3단계는 풀이 비어 fork가 실패한 뒤 **원래 패치의 거부(400 `bad heartbeat`)** 로 돌아간다. 4단계의 정상 사용자는 타깃에서 정상 처리된다. 코드 경로: 프록시 `_fork()`가 `pool.acquire()`에서 None을 받아 `fork_fail`을 남기고 503을 돌려준다(`proxy/proxy.py` 130~133행). 타깃의 `hp_fork()`는 False가 되고, `hp_skip(reject)`이 거부를 실행한다(`server/app.py` 35·42행).
2. **비밀은 새지 않는다(보안 유지).** 대신 3번째 공격자는 패치 모드와 **같은 400 `bad heartbeat`** 를 받는다. 허니패치가 숨기려던 "이 서버는 패치됨"이 드러난다(**기만 실패**).
3. **공격 요청 1개가 미끼 1개를 차지한다.** fork 1회마다 `pool.acquire()`로 미끼 하나가 그 세션에 고정되고, 세션이 다르면 같은 공격자라도 새 미끼를 쓴다. 풀 크기 2이므로 서로 다른 세션 2개로 고갈된다. 세션 ID는 클라이언트가 정하므로(C5) 공격자 한 명이 세션 ID만 바꿔도 된다.
4. **고갈 상태를 유지하는 비용이 작다 (계산, 실행하지 않음).** 미끼는 고정 세션이 `DECOY_TIMEOUT`(30초) 동안 요청이 없어야 반환된다(`proxy/proxy.py` 78행, 감시 주기 1초). 그래서 고정된 세션 2개가 각자 30초 안에 한 번씩 아무 요청이나 보내면 풀이 계속 비어 있다. 요청량은 미끼당 30초에 1개, 풀 크기 N이면 30초에 N개 정도다. 이 동안 다른 공격자는 모두 3단계처럼 400을 받는다.
5. **C8과의 관계:** C8(외부 `/__hp/fork`)이 고쳐지기 전에는 공격 입력 없이 외부 fork만으로 같은 고갈을 만들 수 있다(`evidence/before/i_c8_fork_external.md` 4·6단계). 이 사례는 C8과 섞이지 않도록 정상적인 공격 요청만 썼다.
6. 고정 사례 3종에는 공격 세션이 2개 이하라 `run_demo.py`는 15/15다.

## 원논문 대조 (원문 대조 필요)
원논문 PDF가 저장소에 없어 원문을 직접 확인하지 못했다. 아래는 팀이 정리한 원논문 내용과 이번 결과를 맞춰 본 것이고, 절 번호와 표현은 **원문 대조 필요**다.

| 원논문 (원문 대조 필요) | 이 구현에서 관찰한 것 | 일치 여부 |
|---|---|---|
| §3: fork가 자원 고갈 등으로 조용히 실패하면 기만을 포기하고 원래 패치의 교정 동작을 실행한다 | 3단계: `fork_fail decoy pool empty` → 타깃이 `hp_skip(reject)`로 400 `bad heartbeat` (패치 모드와 같은 응답) | 일치 |
| §7: 공격자가 flooding 등으로 미끼 자원을 고갈시킬 수 있지만, 허니패치 없는 서버에 같은 공격을 한 결과와 관찰상 비슷해 구분하기 어렵다 | 고갈 후 응답은 "패치된 서버"(400)와 같다. "미끼가 있었다"는 사실은 드러나지 않지만 "패치되어 있다"는 사실은 드러난다 | 대체로 일치. 원논문은 "허니패치 없는(패치된) 서버와 구분 어려움"을 한계의 완화 근거로 보고, 이 구현도 같다 |
| (이 구현에서 추가로 관찰) | 미끼 1개 = 공격 1회, 반환은 30초 무요청 후 → 고정 세션 N개가 30초마다 한 번씩 요청하면 고갈 상태를 유지 | 원논문 범위 밖의 수치 (풀 크기·타임아웃이 이 구현의 설정값) |

정리하면, 보안은 유지되지만(진짜 비밀 0) 3번째 공격자부터는 일반 패치처럼 400을 받아 **기만이 실패**한다. 원논문 구조(공격마다 미끼 하나)의 자원 한계라서 **원논문 한계**로 분류하고 코드는 고치지 않는다.

## 로그 발췌 (사례 실행 구간, 시각 `t` 제외)

defender.jsonl (첫 줄은 기동 확인용 `/__health`):
```json
{"event": "route", "session": "anonymous", "to": "target", "status": 200}
{"event": "fork_ok", "session": "attacker-1", "decoy": 9101}
{"event": "route", "session": "attacker-1", "to": "target", "status": 200}
{"event": "route", "session": "attacker-1", "to": "decoy", "status": 200, "replay": true}
{"event": "fork_ok", "session": "attacker-2", "decoy": 9102}
{"event": "route", "session": "attacker-2", "to": "target", "status": 200}
{"event": "route", "session": "attacker-2", "to": "decoy", "status": 200, "replay": true}
{"event": "fork_fail", "session": "attacker-3", "reason": "decoy pool empty"}
{"event": "route", "session": "attacker-3", "to": "target", "status": 400}
{"event": "route", "session": "user-normal", "to": "target", "status": 200}
```

attacker.jsonl:
```json
{"event": "request", "session": "attacker-1", "mode": "honeypatched", "method": "POST", "path": "/heartbeat", "to": "decoy", "status": 200, "resp_len": 64, "leaks": 0, "body_len": 31, "payload_len": 2, "declared_len": 64, "over": 62}
{"event": "request", "session": "attacker-2", "mode": "honeypatched", "method": "POST", "path": "/heartbeat", "to": "decoy", "status": 200, "resp_len": 64, "leaks": 0, "body_len": 31, "payload_len": 2, "declared_len": 64, "over": 62}
{"event": "request", "session": "attacker-3", "mode": "honeypatched", "method": "POST", "path": "/heartbeat", "to": "target", "status": 400, "resp_len": 13, "leaks": 0, "body_len": 31, "payload_len": 2, "declared_len": 64, "over": 62}
```
(user-normal의 정상 요청은 기록 조건에 해당하지 않아 attacker.jsonl에 없다)
