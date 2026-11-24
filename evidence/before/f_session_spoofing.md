# f. 세션 ID 사칭으로 정상 사용자가 미끼로 끌려감

- 기준 커밋: `e77e5cf` (로컬 main. README만 다르고 코드는 `origin/main` `7e41b5c`와 같음, 소스 수정 없이 실행) · 실행 환경: Ubuntu (WSL2), Python 3.12.3
- 수집 스크립트: [`collect.py`](collect.py) · 원자료: [`raw.json`](raw.json) (`"f"` 키)

## 입력
허니패치 모드. ① 진짜 `user-normal`이 hello/5, `GET /files/users.csv` ② attacker-9가 헤더만 `X-Session-Id: user-normal`로 바꿔 hi/64 공격 ③ 진짜 `user-normal`이 다시 hello/5, `GET /files/users.csv` (모두 프록시 경유)

## 실행 명령
```bash
python3 evidence/before/collect.py    # 사례마다 타깃(해당 모드)+프록시를 새로 띄우고 일반 종료로 정리
```

## 출력
| 모드 | 단계 | 경로 | status | 응답 길이 | 진짜 비밀 | 응답 헤더(X-) | 응답 본문(앞 60자) |
|---|---|---|---|---|---|---|---|
| honeypatched | 진짜 user-normal 정상 요청 (사칭 전) | proxy:8080 | 200 | 5 | 0 | - | `hello` |
| honeypatched | 진짜 user-normal 파일 (사칭 전) | proxy:8080 | 200 | 99 | 6 | - | `sid,user,token,ip\ns-alice,alice,9f2c4e81a7b3d065,10.0.0.23\ns` |
| honeypatched | attacker-9 가 X-Session-Id=user-normal 로 공격 hi/64 | proxy:8080 | 200 | 64 | 0 | - | `hie4627646329147c2\|8tm90\|67.5.5.71;03708d8bc0566589\|8q2\|201.` |
| honeypatched | 진짜 user-normal 정상 요청 (사칭 후) | proxy:8080 | 200 | 5 | 0 | - | `hello` |
| honeypatched | 진짜 user-normal 파일 (사칭 후) | proxy:8080 | 200 | 99 | 0 | - | `sid,user,token,ip\ns-marta,marta,19cdb835c44c1b84,31.8.6.47\ns` |

## 관찰
1. 사칭 공격 한 번으로 **`user-normal` 세션이 미끼에 고정**된다(`fork_ok session=user-normal decoy=9101`). 프록시는 세션을 `X-Session-Id` 헤더 값만으로 식별하고, 그 값은 클라이언트가 마음대로 정한다.
2. 사칭 후 진짜 `user-normal`의 요청이 모두 미끼로 간다. hello는 응답이 같아 눈에 띄지 않지만, **파일 요청은 진짜 `s-alice` 대신 가짜 `s-marta` 파일**을 받는다. 정상 사용자에게 가짜 데이터가 전달된 것이다.
3. 사칭 후 진짜 사용자의 정상 요청이 `attacker.jsonl`에 **공격자 행위로 기록**된다(`to=decoy`라서 기록 대상). 공격자 기록에 무고한 사용자가 섞인다.
4. 사칭한 attacker-9는 미끼 풀 하나를 소비했다. 다른 세션 ID로 반복하면 풀이 고갈되어 이후 진짜 공격은 fork 실패 → 400(일반 패치와 같은 응답)으로 떨어진다(12주차 재리뷰의 attacker-3 사례).
5. 고정은 `DECOY_TIMEOUT`(30초) 동안 요청이 없어야 풀린다. 진짜 사용자가 계속 요청하면 타이머가 갱신되어 미끼에 계속 묶인다.

## 로그 발췌 (단계별 증가분, 시각 `t` 제외)

**[honeypatched] 진짜 user-normal 정상 요청 (사칭 전)**

- 요청: `POST /heartbeat` · `X-Session-Id: user-normal` · proxy:8080 · 본문 `{"payload": "hello", "length": 5}`
- 응답 본문 전체: `'hello'`
- defender.jsonl:
  ```json
  {"event": "route", "session": "user-normal", "to": "target", "status": 200}
  ```
- attacker.jsonl:
  - (기록 없음)

**[honeypatched] 진짜 user-normal 파일 (사칭 전)**

- 요청: `GET /files/users.csv` · `X-Session-Id: user-normal` · proxy:8080
- 노출된 진짜 비밀: `9f2c4e81a7b3d065`, `alice`, `10.0.0.23`, `51d8e0c29b7fa364`, `bob`, `172.16.4.150`
- 응답 본문 전체: `'sid,user,token,ip\ns-alice,alice,9f2c4e81a7b3d065,10.0.0.23\ns-bob,bob,51d8e0c29b7fa364,172.16.4.150\n'`
- defender.jsonl:
  ```json
  {"event": "route", "session": "user-normal", "to": "target", "status": 200}
  ```
- attacker.jsonl:
  - (기록 없음)

**[honeypatched] attacker-9 가 X-Session-Id=user-normal 로 공격 hi/64**

- 요청: `POST /heartbeat` · `X-Session-Id: user-normal` · proxy:8080 · 본문 `{"payload": "hi", "length": 64}`
- 응답 본문 전체: `'hie4627646329147c2|8tm90|67.5.5.71;03708d8bc0566589|8q2|201.47.1'`
- defender.jsonl:
  ```json
  {"event": "fork_ok", "session": "user-normal", "decoy": 9101}
  {"event": "route", "session": "user-normal", "to": "target", "status": 200}
  {"event": "route", "session": "user-normal", "to": "decoy", "status": 200, "replay": true}
  ```
- attacker.jsonl:
  ```json
  {"event": "request", "session": "user-normal", "mode": "honeypatched", "method": "POST", "path": "/heartbeat", "to": "decoy", "status": 200, "resp_len": 64, "leaks": 0, "body_len": 31, "payload_len": 2, "declared_len": 64, "over": 62}
  ```

**[honeypatched] 진짜 user-normal 정상 요청 (사칭 후)**

- 요청: `POST /heartbeat` · `X-Session-Id: user-normal` · proxy:8080 · 본문 `{"payload": "hello", "length": 5}`
- 응답 본문 전체: `'hello'`
- defender.jsonl:
  ```json
  {"event": "route", "session": "user-normal", "to": "decoy", "status": 200}
  ```
- attacker.jsonl:
  ```json
  {"event": "request", "session": "user-normal", "mode": "honeypatched", "method": "POST", "path": "/heartbeat", "to": "decoy", "status": 200, "resp_len": 5, "leaks": 0, "body_len": 33, "payload_len": 5, "declared_len": 5, "over": 0}
  ```

**[honeypatched] 진짜 user-normal 파일 (사칭 후)**

- 요청: `GET /files/users.csv` · `X-Session-Id: user-normal` · proxy:8080
- 응답 본문 전체: `'sid,user,token,ip\ns-marta,marta,19cdb835c44c1b84,31.8.6.47\ns-dan,dan,8be66df143ee56d5,198.23.7.204\n'`
- defender.jsonl:
  ```json
  {"event": "route", "session": "user-normal", "to": "decoy", "status": 200}
  ```
- attacker.jsonl:
  ```json
  {"event": "request", "session": "user-normal", "mode": "honeypatched", "method": "GET", "path": "/files/users.csv", "to": "decoy", "status": 200, "resp_len": 99, "leaks": 0}
  ```
