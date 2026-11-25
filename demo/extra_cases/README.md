# 추가 사례 (13주차 반례 탐색)

고정 검증 사례(`demo/fixed_cases.json`)와는 별개다. 고정 사례는 수정하지 않고, 새로 찾는 반례는 여기에 담당별 파일로 추가한다.

| 파일 | 담당 | 대상 |
|---|---|---|
| `server.json` | 전민기 | `server/app.py` |
| `proxy.json` | 김영석 | `proxy/proxy.py` |
| `redact.json` | 이현우 | redaction (`honeypatch/redact.py`) |
| `pool.json` | 우지민 | `proxy/pool.py` |
| `demo.json` | 김태우 | `demo/` |

실행: `python3 demo/run_extra.py [--file proxy.json] [--case C1-negative-length]` → `results/extra_results.md`

## 사례 형식

```json
{
  "id": "C1-negative-length", "owner": "전민기", "direction": "경계값",
  "description": "무엇을 왜 보는지, 근거 파일",
  "written_before_run": true,
  "modes": ["unpatched", "patched", "honeypatched"],
  "steps": [
    {"session": "attacker-neg", "method": "POST", "path": "/heartbeat",
     "body": {"payload": "hello", "length": -1}, "headers": {}, "target": "proxy",
     "expect": {"honeypatched": {"status": 200}}}
  ],
  "expect": {
    "patched": {"status": 400, "len": 13, "leaks": 0, "forks": 0, "route": "target"}
  }
}
```

- **기대 결과는 실행 전에 "올바른 동작"으로 적는다.** 지금 코드의 결과를 보고 맞춰 쓰지 않는다. 다 적었으면 `written_before_run: true`.
- `id`: 반례는 `C번호-짧은-이름` (`docs/counterexamples.md`의 번호와 같게), 대조군은 `CTRL-`, 형식 예시는 `EX-`.
- `steps`: 순서대로 보낸다. 여러 개 가능 (예: 공격 후 같은 세션으로 `/__health`).
  - `target`: `proxy`(기본, 8080) 또는 `target_direct`(타깃 9000에 직접. 프록시 로그가 없으므로 `route`는 `-`).
  - `headers`: 추가 헤더. `X-Session-Id`는 `session` 값으로 자동으로 들어간다.
  - step 안의 `expect`: 그 단계에서 확인할 것 (선택).
- 바깥 `expect`: **마지막 step 기준.** 모드별로 확인할 항목만 적는다. 적지 않은 모드는 실행만 하고 판정하지 않는다.

## expect 항목

| 키 | 뜻 | 예 |
|---|---|---|
| `status` | HTTP 상태 | `400` |
| `len` | 응답 본문 바이트 수 | `64` |
| `leaks` | 응답에 나타난 진짜 비밀 개수 (`config.SEED_USERS`의 token·user·ip, `run_demo.py`와 같은 방식) | `0` |
| `forks` | 그 단계 동안 `defender.jsonl`에 생긴 `fork_ok` 수 | `1` |
| `route` | 그 단계의 마지막 `route` 이벤트 (`target` / `decoy`) | `"decoy"` |
| `body` | 응답 본문이 정확히 같음 | `"hello"` |
| `body_contains` / `body_not_contains` | 본문에 문자열이 있음 / 없음 | `"s-alice"` |
| `same_as_step` | N단계(1부터)와 status·본문이 같음 | `1` |

숫자 항목은 `">0"`, `">=1"`, `"<=64"`처럼 비교식도 쓸 수 있다.
