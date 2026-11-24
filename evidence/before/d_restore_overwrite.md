# d. 공격자가 /__hp/restore로 미끼 상태를 덮어씀

- 기준 커밋: `e77e5cf` (로컬 main. README만 다르고 코드는 `origin/main` `7e41b5c`와 같음, 소스 수정 없이 실행) · 실행 환경: Ubuntu (WSL2), Python 3.12.3
- 수집 스크립트: [`collect.py`](collect.py) · 원자료: [`raw.json`](raw.json) (`"d"` 키)

## 입력
허니패치 모드. ① 고정 안 된 `user-z`가 `POST /__hp/restore` `{"state":{"sessions":[]}}` (비교용) ② `attacker-1` 공격 hi/64 ③ 같은 `attacker-1`이 `POST /__hp/restore` `{"state":{"sessions":[]}}` ④ `attacker-1` 공격 hi/64 다시 (모두 프록시 경유)

## 실행 명령
```bash
python3 evidence/before/collect.py    # 사례마다 타깃(해당 모드)+프록시를 새로 띄우고 일반 종료로 정리
```

## 출력
| 모드 | 단계 | 경로 | status | 응답 길이 | 진짜 비밀 | 응답 헤더(X-) | 응답 본문(앞 60자) |
|---|---|---|---|---|---|---|---|
| honeypatched | 고정 안 된 세션의 /__hp/restore (비교용) | proxy:8080 | 404 | 9 | 0 | - | `not found` |
| honeypatched | attacker-1 공격 hi/64 (1차) | proxy:8080 | 200 | 64 | 0 | - | `hi47f1f1142896bfb3\|bdr6f\|33.1.7.64;4b06446639f2e8ba\|0l5\|220.` |
| honeypatched | attacker-1 /__hp/restore 빈 세션 | proxy:8080 | 200 | 8 | 0 | - | `restored` |
| honeypatched | attacker-1 공격 hi/64 (2차) | proxy:8080 | 200 | 38 | 0 | - | `hi0000000000000000\|attacker\|127.0.0.1;` |

## 관찰
1. 고정 안 된 세션은 타깃으로 가서 404(타깃은 `ROLE == "decoy"`일 때만 restore 허용). 그러나 **미끼에 고정된 공격자의 restore는 미끼로 전달되어 `200 restored`** 가 된다. 외부 요청으로 방어자 내부 API가 실행된다.
2. 그 뒤 같은 공격의 응답이 **64바이트 가짜 힙 → 38바이트 `hi0000000000000000|attacker|127.0.0.1;`** 로 바뀐다. 다른 사용자(가짜) 레코드가 사라졌고, 선언 길이 64보다 응답이 짧아져 미패치 서버와 형식이 달라진다. 공격자는 restore가 통한다는 것 자체로 미끼임을 확인할 수 있다.
3. 원인(코드): 프록시가 외부에서 온 `/__hp/*` 경로를 막지 않고(proxy.py 146~151행, `/__hp/fork`만 따로 처리), 미끼의 `do_POST`(server/app.py 86~89행)는 요청 출처를 확인하지 않는다.
4. restore 요청은 `attacker.jsonl`에 남지 않는다(`/__` 제외). `defender.jsonl`에는 `route to=decoy status=200`만 남아 상태가 덮어써진 사실이 드러나지 않는다.
5. 실제 비밀 노출은 없다(덮어쓴 대상이 이미 redaction된 미끼). 피해는 기만 실패와 미끼 상태 조작.

## 로그 발췌 (단계별 증가분, 시각 `t` 제외)

**[honeypatched] 고정 안 된 세션의 /__hp/restore (비교용)**

- 요청: `POST /__hp/restore` · `X-Session-Id: user-z` · proxy:8080 · 본문 `{"state": {"sessions": []}}`
- 응답 본문 전체: `'not found'`
- defender.jsonl:
  ```json
  {"event": "route", "session": "user-z", "to": "target", "status": 404}
  ```
- attacker.jsonl:
  - (기록 없음)

**[honeypatched] attacker-1 공격 hi/64 (1차)**

- 요청: `POST /heartbeat` · `X-Session-Id: attacker-1` · proxy:8080 · 본문 `{"payload": "hi", "length": 64}`
- 응답 본문 전체: `'hi47f1f1142896bfb3|bdr6f|33.1.7.64;4b06446639f2e8ba|0l5|220.85.2'`
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

**[honeypatched] attacker-1 /__hp/restore 빈 세션**

- 요청: `POST /__hp/restore` · `X-Session-Id: attacker-1` · proxy:8080 · 본문 `{"state": {"sessions": []}}`
- 응답 본문 전체: `'restored'`
- defender.jsonl:
  ```json
  {"event": "route", "session": "attacker-1", "to": "decoy", "status": 200}
  ```
- attacker.jsonl:
  - (기록 없음)

**[honeypatched] attacker-1 공격 hi/64 (2차)**

- 요청: `POST /heartbeat` · `X-Session-Id: attacker-1` · proxy:8080 · 본문 `{"payload": "hi", "length": 64}`
- 응답 본문 전체: `'hi0000000000000000|attacker|127.0.0.1;'`
- defender.jsonl:
  ```json
  {"event": "route", "session": "attacker-1", "to": "decoy", "status": 200}
  ```
- attacker.jsonl:
  ```json
  {"event": "request", "session": "attacker-1", "mode": "honeypatched", "method": "POST", "path": "/heartbeat", "to": "decoy", "status": 200, "resp_len": 38, "leaks": 0, "body_len": 31, "payload_len": 2, "declared_len": 64, "over": 62}
  ```
