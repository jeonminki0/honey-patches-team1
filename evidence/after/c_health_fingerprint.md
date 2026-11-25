# c. 미끼 고정 세션의 /__health가 미끼임을 드러냄 - 수정 후

- 수정 커밋: 이 브랜치 (`feat/proxy-internal-paths`) - 기준: `origin/main` `5d136e4`
- 실행 환경: Windows 11 Pro 10.0.26200 (네이티브), Python 3.13.14
- 수집 스크립트: [`collect_internal_paths.py`](collect_internal_paths.py)
- 수정 전 기록: [`../before/c_health_fingerprint.md`](../before/c_health_fingerprint.md)

## 입력

수정 전과 같다. 허니패치 모드에서 1) `user-normal`이 `GET /__health` 2) `attacker-1`이 `{"payload":"hi","length":64}` 공격 3) 같은 `attacker-1`이 `GET /__health`. 모두 프록시 경유.

대조군으로 **없는 경로** `GET /nope`을 하나 더 보냈다. 차단된 내부 경로와 구분되는지 보기 위해서다.

## 실행 명령

```bash
python server/app.py --mode honeypatched --role target --port 9000
python proxy/proxy.py
python evidence/after/collect_internal_paths.py
```

## 출력

| 단계 | 요청 | status | 응답 길이 | 진짜 비밀 | 응답 본문 |
|---|---|---|---|---|---|
| 정상 사용자 /__health (비교용) | `GET /__health` | 404 | 9 | 0 | `not found` |
| attacker-1 공격 hi/64 | `POST /heartbeat` | 200 | 64 | 0 | `hi3794e8d60a402a99\|3ax55\|66.4.1.77;...` |
| attacker-1 /__health | `GET /__health` | 404 | 9 | 0 | `not found` |
| 없는 경로 (대조군) | `GET /nope` | 404 | 9 | 0 | `not found` |

## 수정 전후 비교

| | 수정 전 | 수정 후 |
|---|---|---|
| 정상 사용자 `/__health` | `target:honeypatched` | `not found` |
| 미끼 고정 공격자 `/__health` | **`decoy:honeypatched`** | `not found` |
| 두 응답이 다른가 | **다르다** (미끼 판별 가능) | 같다 |
| 없는 경로와 구분되는가 | 구분됨 | **구분 안 됨** |

## 관찰

1. 미끼에 고정된 공격자와 정상 사용자가 **같은 응답**을 받는다. 응답만으로 미끼 여부를 알 수 없다.
2. 차단된 내부 경로의 응답(`404 not found`, 9바이트)이 **없는 경로의 응답과 글자 하나까지 같다.** 타깃 `server/app.py`가 모르는 경로에 주는 응답과 동일한 값을 쓴다. 그래서 공격자는 "그런 경로가 없다"와 "막혀 있다"를 구분할 수 없다.
3. 모드 이름(`honeypatched`)도 더 이상 나가지 않는다.
4. 프록시 자신은 여전히 타깃 모드를 안다. `attacker.jsonl`의 `"mode": "honeypatched"`가 그대로 찍힌다. `target_mode()`는 `_handle()`을 거치지 않고 타깃에 직접 묻기 때문이다.

## 수정 내용

`proxy/proxy.py` `_handle()`. `/__hp/fork`는 프록시가 직접 처리하므로 그대로 두고, 그 밖의 `/__` 경로는 타깃이나 미끼로 넘기지 않는다.

```python
if self.path == "/__hp/fork":
    return self._fork(raw)
if self.path.startswith("/__"):
    dlog("blocked", session=..., method=method, path=self.path)
    return self._reply(404, b"not found")
```

## 로그 발췌

**[honeypatched] attacker-1 /__health**

- 요청: `GET /__health` - `X-Session-Id: attacker-1`
- 응답 본문 전체: `'not found'`
- defender.jsonl:
  ```json
  {"event": "blocked", "session": "attacker-1", "method": "GET", "path": "/__health"}
  ```
- attacker.jsonl:
  - (기록 없음)

막힌 요청은 `defender.jsonl`에 `blocked`로 남는다. 수정 전에는 `route to=decoy`만 남아서 내부 경로가 미끼까지 갔다는 사실이 드러나지 않았다.

## 남은 것

공격자가 보내는 `X-Session-Id`를 바꿔 가며 세션을 새로 만드는 문제는 이 수정으로 막히지 않는다. 별도 반례(`f_session_spoofing`)로 둔다.

## 재실행 확인

같은 브랜치에서 `python demo/run_demo.py` 판정 15건 모두 통과. `tests/decoy_pool/check_release.py` 6건 모두 통과, `check_files.py` 5건 모두 통과.

`run_demo.py`의 `wait_up()`은 `/__health`가 404를 줘도 기동 성공으로 본다(`if getattr(e, "code", None): return True`). 미끼 기동 확인은 `proxy/pool.py`가 미끼 포트에 직접 묻기 때문에 프록시를 거치지 않는다.
