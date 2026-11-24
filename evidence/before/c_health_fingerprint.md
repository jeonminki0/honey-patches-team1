# c. 미끼 고정 세션의 /__health가 미끼임을 드러냄

- 기준 커밋: `e77e5cf` (로컬 main. README만 다르고 코드는 `origin/main` `7e41b5c`와 같음, 소스 수정 없이 실행) · 실행 환경: Ubuntu (WSL2), Python 3.12.3
- 수집 스크립트: [`collect.py`](collect.py) · 원자료: [`raw.json`](raw.json) (`"c"` 키)

## 입력
허니패치 모드. ① `user-normal`이 `GET /__health` ② `attacker-1`이 `{"payload":"hi","length":64}` 공격 ③ 같은 `attacker-1`이 `GET /__health` (모두 프록시 경유)

## 실행 명령
```bash
python3 evidence/before/collect.py    # 사례마다 타깃(해당 모드)+프록시를 새로 띄우고 일반 종료로 정리
```

## 출력
| 모드 | 단계 | 경로 | status | 응답 길이 | 진짜 비밀 | 응답 헤더(X-) | 응답 본문(앞 60자) |
|---|---|---|---|---|---|---|---|
| honeypatched | 정상 사용자 /__health (비교용) | proxy:8080 | 200 | 19 | 0 | - | `target:honeypatched` |
| honeypatched | attacker-1 공격 hi/64 | proxy:8080 | 200 | 64 | 0 | - | `hib2e6aa774236a41e\|cqe4a\|22.5.5.58;e5474fdfbcb81117\|ah6\|241.` |
| honeypatched | attacker-1 /__health | proxy:8080 | 200 | 18 | 0 | - | `decoy:honeypatched` |

## 관찰
1. 정상 사용자는 `target:honeypatched`, 미끼에 고정된 공격자는 **`decoy:honeypatched`**를 받는다. 문자열 하나로 '내가 미끼에 있다'는 것을 알 수 있어 허니패치의 기만이 깨진다. 모드 이름도 그대로 노출된다.
2. 원인(코드): 프록시 `_handle()`은 경로를 구분하지 않고 고정된 미끼로 전달하고(proxy.py 150~151행), 서버 `do_GET`(server/app.py 74행)은 `/__health`에 `{ROLE}:{MODE}`를 그대로 돌려준다.
3. `/__health` 요청은 `attacker.jsonl`에 남지 않는다(proxy.py 164행 `/__` 제외). `defender.jsonl`에는 `route to=decoy`만 남는다.

## 로그 발췌 (단계별 증가분, 시각 `t` 제외)

**[honeypatched] 정상 사용자 /__health (비교용)**

- 요청: `GET /__health` · `X-Session-Id: user-normal` · proxy:8080
- 응답 본문 전체: `'target:honeypatched'`
- defender.jsonl:
  ```json
  {"event": "route", "session": "user-normal", "to": "target", "status": 200}
  ```
- attacker.jsonl:
  - (기록 없음)

**[honeypatched] attacker-1 공격 hi/64**

- 요청: `POST /heartbeat` · `X-Session-Id: attacker-1` · proxy:8080 · 본문 `{"payload": "hi", "length": 64}`
- 응답 본문 전체: `'hib2e6aa774236a41e|cqe4a|22.5.5.58;e5474fdfbcb81117|ah6|241.97.0'`
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

**[honeypatched] attacker-1 /__health**

- 요청: `GET /__health` · `X-Session-Id: attacker-1` · proxy:8080
- 응답 본문 전체: `'decoy:honeypatched'`
- defender.jsonl:
  ```json
  {"event": "route", "session": "attacker-1", "to": "decoy", "status": 200}
  ```
- attacker.jsonl:
  - (기록 없음)
