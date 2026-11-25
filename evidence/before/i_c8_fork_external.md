# i. C8: 외부 요청으로 /__hp/fork를 실행해 세션 고정·미끼 상태 주입·풀 고갈

- 기준 커밋: `5d136e4` (main, 소스 수정 없이 실행) · 실행 환경: Ubuntu (WSL2), Python 3.12.3
- 수집 스크립트: [`collect_c8.py`](collect_c8.py) · 처음 발견: PR #20 리뷰 [3]
- 같은 실행에서 C9(절대 URI), C10(미끼 포트 직접 접근)도 함께 기록했다 (아래 "참고" 절)

## 입력
허니패치 모드. 모든 요청은 프록시(8080) 경유이고, 요청 줄을 정규화 없이 소켓으로 보낸다.
1. 진짜 `user-normal`: `POST /heartbeat {"payload":"hello","length":5}`, `GET /files/users.csv` (fork 전)
2. 외부 클라이언트(`X-Session-Id: anyone`): `POST /__hp/fork {"session":"user-normal","state":{"sessions":[]}}`
3. 진짜 `user-normal`: 1과 같은 요청 두 개 (fork 후)
4. 외부 클라이언트: `POST /__hp/fork {"session":"attacker-9","state":{"sessions":[{"sid":"zz","token":"INJECTED_BY_FORK","user":"evil","ip":"6.6.6.6"}]}}`
5. `attacker-9`: `POST /heartbeat {"payload":"hi","length":64}`
6. 풀이 고갈된 뒤 진짜 공격 `attacker-1`: `POST /heartbeat {"payload":"hi","length":64}`

## 실행 명령
```bash
python3 evidence/before/collect_c8.py    # 사례마다 타깃(honeypatched)+프록시를 새로 띄우고 일반 종료로 정리
```

## 출력

| 단계 | 요청 | status | 길이 | 진짜 비밀 | 응답 본문(앞부분) | defender.jsonl |
|---|---|---|---|---|---|---|
| 1 | user-normal hello/5 (fork 전) | 200 | 5 | 0 | `hello` | route **target** |
| 1 | user-normal `/files/users.csv` (fork 전) | 200 | 99 | 6 | `s-alice,alice,9f2c4e81a7b3d065,…` | route target |
| 2 | **외부** `POST /__hp/fork` (session user-normal) | **200** | 6 | 0 | `forked` | **`fork_ok session=user-normal decoy=9101`** |
| 3 | user-normal hello/5 (fork 후) | 200 | 5 | 0 | `hello` | route **decoy** |
| 3 | user-normal `/files/users.csv` (fork 후) | 200 | 99 | 0 | **`s-marta,marta,19cdb835c44c1b84,…`** (가짜) | route decoy |
| 4 | **외부** `POST /__hp/fork` (session attacker-9, 상태 주입) | **200** | 6 | 0 | `forked` | `fork_ok session=attacker-9 decoy=9102` |
| 5 | attacker-9 hi/64 | 200 | 64 | 0 | **`hiINJECTED_BY_FORK\|evil\|6.6.6.6;0000000000000000\|attacker\|127.0.`** | route decoy |
| 6 | 진짜 공격 attacker-1 hi/64 | **400** | 13 | 0 | `bad heartbeat` | **`fork_fail reason="decoy pool empty"`**, route target 400 |

attacker.jsonl:
```json
{"event": "request", "session": "user-normal", "mode": "honeypatched", "method": "POST", "path": "/heartbeat", "to": "decoy", "status": 200, "resp_len": 5, "leaks": 0, "body_len": 33, "payload_len": 5, "declared_len": 5, "over": 0}
{"event": "request", "session": "user-normal", "mode": "honeypatched", "method": "GET", "path": "/files/users.csv", "to": "decoy", "status": 200, "resp_len": 99, "leaks": 0}
{"event": "request", "session": "attacker-9", "mode": "honeypatched", "method": "POST", "path": "/heartbeat", "to": "decoy", "status": 200, "resp_len": 64, "leaks": 0, "body_len": 31, "payload_len": 2, "declared_len": 64, "over": 62}
{"event": "request", "session": "attacker-1", "mode": "honeypatched", "method": "POST", "path": "/heartbeat", "to": "target", "status": 400, "resp_len": 13, "leaks": 0, "body_len": 31, "payload_len": 2, "declared_len": 64, "over": 62}
```
(외부 `/__hp/fork` 요청 2건 자체는 attacker.jsonl에 없다)

## 관찰
1. **프록시는 `/__hp/fork`를 누가 보냈는지 확인하지 않는다.** `proxy/proxy.py` 146~147행은 경로 문자열만 보고 `_fork()`를 실행한다. 타깃의 `hp_fork()`(`honeypatch/hp.py` 24~26행)도 외부 클라이언트와 똑같이 공개 포트 8080으로 평범한 POST를 보낸다. 헤더, 비밀값, 다른 포트 같은 구분 장치가 없다. 출발지 IP도 둘 다 127.0.0.1이다.
2. **요청 한 줄로 아무 세션이나 미끼에 가둘 수 있다(2~3단계).** 공격 입력을 보내지 않았는데도 진짜 `user-normal`이 미끼에 고정되어, 진짜 파일(`s-alice`, 비밀 6건) 대신 가짜 파일(`s-marta`)을 받는다. C5(세션 사칭)는 위반 입력을 보내야 하지만, C8은 fork를 직접 부르므로 더 쉽다.
3. **미끼 내용을 공격자가 마음대로 채울 수 있다(4~5단계).** `state`가 검사 없이 미끼의 `/__hp/restore`로 넘어가, 응답에 공격자가 쓴 `INJECTED_BY_FORK|evil|6.6.6.6`이 나온다. C3(외부 restore)와 결과가 같고, 경로가 `/__hp/fork`라 C3를 막아도 남는다.
4. **외부 fork 두 번으로 미끼 풀(2개)이 고갈되고, 이후 진짜 공격은 허니패치 대신 400 거부를 받는다(6단계).** 일반 패치와 같은 응답이라 허니패치가 무력화된다. C6(풀 고갈)을 공격 입력 없이 일으킨다.
5. **방어자 로그로 구분하기 어렵다.** 외부 fork도 `defender.jsonl`에 정상 fork와 같은 `fork_ok`로 남는다. 정상 fork 앞에는 같은 세션의 `route to=target`(위반 요청)이 있지만, 외부 fork 앞에는 없다는 순서 차이뿐이다. 요청 자체는 `/__` 경로라 `attacker.jsonl`에도 남지 않는다.
6. PR #20(C2·C3 수정)은 `/__hp/fork`만 일부러 열어 두므로, merge돼도 이 문제는 그대로다. 막으려면 타깃의 fork 요청과 외부 요청을 구분할 장치가 필요하다(예: 프록시가 127.0.0.1의 별도 제어 포트에서만 fork를 받고 `hp.py`가 그 포트로 보냄). 그러면 `proxy/proxy.py`(김영석), `honeypatch/hp.py`(전민기), `honeypatch/config.py`(이현우)를 함께 바꿔야 한다.
7. 고정 사례 3종에는 외부 fork 입력이 없어 `run_demo.py`는 15/15다.

## 참고: 같은 실행의 C9·C10

### C9: 절대 URI 요청에 프록시가 응답 없이 연결을 끊음

| 단계 | 요청 | status | 본문 | defender.jsonl |
|---|---|---|---|---|
| 1 | 프록시에 `GET http://127.0.0.1:9101/__health` | **응답 없이 끊김** | (없음) | (기록 없음) |
| 2 | 타깃 직접 같은 요청 (비교용) | 404 | `not found` | - |
| 3 | 프록시에 `GET /nope` (비교용) | 404 | `not found` | route target 404 |

- 원인(코드): `forward()`(`proxy/proxy.py` 92행)가 `f"http://{config.HOST}:{port}{path}"`로 URL을 만든다. 경로가 절대 URI면 `http://127.0.0.1:9000http://127.0.0.1:9101/__health`가 되어 요청이 실패하고, 처리 중 예외로 연결이 끊긴다. route 로그도 남지 않는다.
- 같은 요청을 타깃에 직접 보내면 404인데 프록시는 연결을 끊으므로, 앞에 프록시가 있다는 것이 드러난다. 미끼와 타깃을 구분하는 정보는 아니다.

### C10: 프록시를 거치지 않고 미끼 포트에 직접 접근

| 단계 | 요청 | status | 본문 |
|---|---|---|---|
| 1 | attacker-1 공격 hi/64 (프록시 경유) | 200 | 64바이트 가짜 힙 (`fork_ok decoy=9101`) |
| 2 | **미끼 9101에 직접** `POST /__hp/restore {INJECTED00000000}` | **200** | `restored` |
| 3 | attacker-1 hi/64 (프록시 경유) | 200 | **31바이트 `hiINJECTED00000000\|INJ\|6.6.6.6;`** |
| 4 | 미끼 9101에 직접 `GET /__health` | 200 | `decoy:honeypatched` |

- 미끼 포트에 직접 닿으면 상태 덮어쓰기와 미끼 확인이 모두 된다. 모든 포트가 127.0.0.1에 열려 있기 때문이다.
- 우리 위협 모델은 "공격자는 프록시(8080)에만 접근한다"이므로 그 밖의 일이다. 원논문도 미끼를 격리된 컨테이너에 둔다. 그래서 수정 대상이 아니라 **명세상 미지원**으로 문서화한다.
