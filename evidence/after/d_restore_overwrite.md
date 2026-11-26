# d. 외부에서 온 /__hp/restore로 미끼 상태를 덮어씀 - 수정 후

- 수정 커밋: 이 브랜치 (`feat/proxy-internal-paths`) - 기준: `origin/main` `5d136e4`
- 실행 환경: Windows 11 Pro 10.0.26200 (네이티브), Python 3.13.14
- 수집 스크립트: [`collect_internal_paths.py`](collect_internal_paths.py)
- 수정 전 기록: [`../before/d_restore_overwrite.md`](../before/d_restore_overwrite.md)

## 입력

허니패치 모드. 1) `attacker-1`이 `{"payload":"hi","length":64}`로 공격해 미끼에 고정된다. 2) 같은 세션이 프록시로 `POST /__hp/restore`를 보내 미끼 상태를 자기 값으로 덮어쓰려 한다. 3) 다시 같은 공격을 보내 응답이 바뀌었는지 본다.

주입할 값:

```json
{"state": {"sessions": [{"sid": "x", "token": "INJECTED_BY_ATTACKER", "user": "x", "ip": "1.1.1.1"}]}}
```

## 실행 명령

```bash
python server/app.py --mode honeypatched --role target --port 9000
python proxy/proxy.py
python evidence/after/collect_internal_paths.py
```

## 출력

| 단계 | 요청 | status | 응답 길이 | 응답 본문 |
|---|---|---|---|---|
| attacker-1 공격 hi/64 | `POST /heartbeat` | 200 | 64 | `hi3794e8d60a402a99\|3ax55\|66.4.1.77;...` |
| attacker-1 /__hp/restore 주입 | `POST /__hp/restore` | **404** | 9 | `not found` |
| 주입 뒤 공격 hi/64 | `POST /heartbeat` | 200 | 64 | `hi3794e8d60a402a99\|3ax55\|66.4.1.77;...` |

## 수정 전후 비교

| | 수정 전 | 수정 후 |
|---|---|---|
| `/__hp/restore` 응답 | `200 restored` | `404 not found` |
| 주입이 미끼에 닿는가 | **닿는다** | 안 닿는다 |
| 주입 뒤 공격 응답 | `hiINJECTED_BY_ATTACKER\|x\|1.1.1.1;...` | `hi3794e8d60a402a99\|3ax55\|66.4.1.77;...` |
| 주입 전후 응답이 같은가 | **다르다** | 같다 |

## 관찰

1. 주입 요청이 미끼에 도달하지 않는다. 프록시에서 404로 끊긴다.
2. **주입 전후의 공격 응답이 바이트까지 같다.** 미끼 상태가 바뀌지 않았다는 뜻이다. 수정 전에는 공격자가 쓴 `INJECTED_BY_ATTACKER` 문자열이 다음 공격 응답에 그대로 실려 나왔다.
3. 404 응답이 없는 경로(`GET /nope`)와 같아서, 공격자는 그 경로가 막혀 있다는 사실조차 알 수 없다.
4. 미끼 내부의 정상 경로(`/__hp/restore`)는 그대로 살아 있다. 프록시가 fork를 처리할 때 `forward()`로 미끼에 직접 호출하기 때문이다. 외부 요청만 막혔다.

## 왜 중요한가

수정 전 구조에서는 미끼가 공격자 입력을 되돌려주는 거울이 된다. 공격자가 자기가 쓴 문자열을 응답에서 다시 보면, 그 서버가 자기 입력을 그대로 저장한다는 사실을 알게 된다. 진짜 서버라면 다른 사용자의 비밀이 나와야 할 자리라서, 기만이 유지되지 않는다.

원논문은 미끼가 진짜 프로세스의 복제본이고 공격자에게 제어 API를 열어 두지 않는다. 이 구멍은 원논문의 한계가 아니라 축소 구현에서 내부 제어 경로를 프록시 바깥에 노출한 구현 버그다.

## 수정 내용

[`c_health_fingerprint.md`](c_health_fingerprint.md)와 같은 한 곳이다. `proxy/proxy.py` `_handle()`에서 `/__hp/fork` 외의 `/__` 경로를 타깃이나 미끼로 넘기지 않는다.

## 로그 발췌

**[honeypatched] attacker-1 /__hp/restore 주입**

- 요청: `POST /__hp/restore` - `X-Session-Id: attacker-1`
- 응답 본문 전체: `'not found'`
- defender.jsonl:
  ```json
  {"event": "blocked", "session": "attacker-1", "method": "POST", "path": "/__hp/restore"}
  ```
- attacker.jsonl:
  - (기록 없음)

**[honeypatched] 주입 뒤 attacker-1 공격 hi/64**

- defender.jsonl:
  ```json
  {"event": "route", "session": "attacker-1", "to": "decoy", "status": 200}
  ```
- attacker.jsonl:
  ```json
  {"event": "request", "session": "attacker-1", "mode": "honeypatched", "method": "POST",
   "path": "/heartbeat", "to": "decoy", "status": 200, "resp_len": 64, "leaks": 0,
   "body_len": 31, "payload_len": 2, "declared_len": 64, "over": 62}
  ```

`fork_ok`가 없다. 이미 고정된 세션이라 미끼로 바로 갔고, 미끼 상태도 그대로다.

## 재실행 확인

같은 브랜치에서 `python demo/run_demo.py` 판정 15건 모두 통과. `tests/decoy_pool/check_release.py` 6건 모두 통과, `check_files.py` 5건 모두 통과.
