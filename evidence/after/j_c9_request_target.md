# j. C9: 요청 줄이 origin-form 이 아닐 때 프록시 응답이 타깃과 달라짐 (수정 후)

- 기준: main `b4067ab` (PR #20 머지 포함) 위에 이 PR 의 `proxy/proxy.py` 수정을 얹은 상태 (브랜치 `fix/c9-request-target`)
- 실행 환경: Windows 11 Pro 10.0.26200 (네이티브), Python 3.13.14
- 수정 전 기록: [`evidence/before/i_c8_fork_external.md`](../before/i_c8_fork_external.md) 의 "참고: 같은 실행의 C9" 절 (우지민 기록, Ubuntu WSL2 / Python 3.12.3), Issue #23
- 수집 스크립트: [`request_target_parity.py`](request_target_parity.py)

수정 전 기록에는 절대 URI 한 가지만 있다. 같은 원인에서 나오는 다른 요청 줄까지 묶어 재려고 사례를 13가지로 늘렸고, 수정 전 수치도 같은 스크립트로 다시 받았다.

## 입력

허니패치 모드. 요청 줄을 정규화하지 않고 소켓으로 글자 그대로 보낸다. 같은 요청을 **프록시(8080)** 와 **타깃(9000) 직접** 양쪽에 보낸다.

판정 기준은 둘로 나뉜다. 공격자는 프록시(8080)만 두드리므로, 어느 쪽이든 "앞에 프록시가 있다"는 사실이 응답 차이로 드러나면 안 된다는 목적은 같다.

1. **보통 경로**는 같은 요청을 타깃에 직접 보낸 응답과 status 와 본문까지 같아야 한다. 프록시가 요청 줄을 고쳐서 보내면 여기서 어긋난다. C9 가 잡는 지점이다.
2. **내부 제어 경로(`/__`)** 는 오히려 타깃 직접과 같으면 안 된다. 타깃은 `/__health` 에 미끼인지 아닌지를 그대로 답하는데(반례 C2), 프록시는 PR #20 에서 이 경로를 막기로 했다. 그래서 기준을 타깃 직접이 아니라 "없는 경로(`/nope`)에 프록시가 주는 404"로 잡는다. 공격자가 실제로 맞대어 볼 수 있는 것이 그 둘이고, 구분이 안 되면 프록시는 그냥 그런 경로가 없는 서버로 보인다. `/nope` 자체는 1번 기준으로 따로 재므로, 2번이 통과하면 내부 경로 = 프록시의 없는 경로 = 타깃의 없는 경로 로 이어진다.

내부 경로는 `forward()` 에 닿기 전에 막히므로 C9 의 원인(요청 줄 재해석)이 거기까지 가지 않는다. 2번 기준이 C9 를 가려 주지는 않는다. 아래 수정 전 표에서 내부 경로 3건을 뺀 10건 중 5건이 어긋난 것이 그 근거다.

## 실행 명령

```bash
# 타깃(honeypatched)과 프록시를 먼저 띄운 뒤
python3 evidence/after/request_target_parity.py
python3 demo/run_extra.py --case C9-request-target
```

## 출력

### 수정 전 (13건 중 5건이 기준과 다름, exit=1)

`proxy/proxy.py` 만 main `b4067ab` 판으로 되돌려 받았다. #20 의 내부 경로 차단은 들어 있고 C9 수정만 빠진 상태다.

| 사례 | 기준 | 프록시(8080) | 기준 응답 | 판정 |
|---|---|---|---|---|
| 절대 URI (미끼 포트) | 타깃 직접 | **응답 없음(연결 끊김)** | 404 `not found` | 다름 |
| 절대 URI (타깃 포트) | 타깃 직접 | **응답 없음(연결 끊김)** | 404 `not found` | 다름 |
| 절대 URI (외부 호스트) | 타깃 직접 | **응답 없음(연결 끊김)** | 404 `not found` | 다름 |
| 조각(#) 붙은 경로 `/heartbeat#x` | 타깃 직접 | **200 `hi`** | 404 `not found` | 다름 |
| 경로가 `/` 로 시작하지 않음 | 타깃 직접 | **응답 없음(연결 끊김)** | 404 `not found` | 다름 |
| 조각(#) 붙은 내부 경로 `/__health#x` | 없는 경로 | 404 `not found` | 404 `not found` | 같음 |
| 질의문(?) 붙은 경로 | 타깃 직접 | 404 `not found` | 404 `not found` | 같음 |
| 점 경로 `/files/../__health` | 타깃 직접 | 404 `not found` | 404 `not found` | 같음 |
| 슬래시 두 개 `//__health` | 없는 경로 | 404 `not found` | 404 `not found` | 같음 |
| 퍼센트 인코딩 `/%5f%5fhealth` | 타깃 직접 | 404 `not found` | 404 `not found` | 같음 |
| 대문자 경로 `/__HEALTH` | 없는 경로 | 404 `not found` | 404 `not found` | 같음 |
| 없는 경로 `/nope` (대조군) | 타깃 직접 | 404 `not found` | 404 `not found` | 같음 |
| 정상 `heartbeat` (대조군) | 타깃 직접 | 200 `hi` | 200 `hi` | 같음 |

### 수정 후 (13건 중 0건이 기준과 다름, exit=0)

위 13가지 모두 프록시 응답이 기준과 status 와 본문까지 같다. 바뀐 다섯 줄만 적으면 이렇다.

| 사례 | 수정 전 프록시 | 수정 후 프록시 | 기준 응답 |
|---|---|---|---|
| 절대 URI (미끼 포트) | 응답 없음(연결 끊김) | **404 `not found`** | 404 `not found` (타깃 직접) |
| 절대 URI (타깃 포트) | 응답 없음(연결 끊김) | **404 `not found`** | 404 `not found` (타깃 직접) |
| 절대 URI (외부 호스트) | 응답 없음(연결 끊김) | **404 `not found`** | 404 `not found` (타깃 직접) |
| `/heartbeat#x` | 200 `hi` | **404 `not found`** | 404 `not found` (타깃 직접) |
| 경로가 `/` 로 시작하지 않음 | 응답 없음(연결 끊김) | **404 `not found`** | 404 `not found` (타깃 직접) |

나머지 8건은 수정 전후가 같다. 그중 내부 경로 3건(`/__health#x`, `//__health`, `/__HEALTH`)은 #20 차단이 `forward()` 보다 먼저 걸린다.

### run_extra 사례

`demo/extra_cases/proxy.json` 에 `C9-request-target` 을 넣었다. 1, 3단계는 타깃 직접(대조군), 2, 4단계는 같은 요청을 프록시로 보내 `same_as_step` 으로 맞대어 본다. 네 단계 모두 내부 경로가 아니므로 #20 머지와 무관하다.

수정 전 (8개 항목 중 4건 어김):

```
| 2 | same_as_step | 1 | "ERR RemoteDisconnected '' ≠ 1단계 404 'not found'" | FAIL |
| 4 | same_as_step | 3 | "200 'hi' ≠ 3단계 404 'not found'"                   | FAIL |
| 4 | status       | 404 | 200                                                | FAIL |
| 4 | body         | "not found" | "hi"                                      | FAIL |
```

수정 후 (8개 항목 모두 통과):

```
| 1 | status | 404 | 404 | PASS |            | 3 | status | 404 | 404 | PASS |
| 1 | body   | "not found" | "not found" | PASS |  | 3 | body | "not found" | "not found" | PASS |
| 2 | same_as_step | 1 | "404 'not found'" | PASS | | 4 | same_as_step | 3 | "404 'not found'" | PASS |
                                                    | 4 | status | 404 | 404 | PASS |
                                                    | 4 | body | "not found" | "not found" | PASS |
```

### 회귀

- `python demo/run_demo.py`: **15/15 통과**. fork 와 재전송 경로가 그대로 돈다(`X-HP-Forked` 판정 포함).
- `python demo/run_extra.py` 전체: 17건 중 5건 어김. 어긴 것은 `C1` patched 와 honeypatched, `C4` unpatched(전민기), `C5`(이현우), `C8`(Issue #22)다. `C2`, `C3` 는 #20 머지로 통과로 바뀌었고, 이 브랜치가 담당하는 `C9` 도 통과다.
- `check_files`, `check_release`, `check_timeout`, `check_orphan` 네 종 모두 PASS. 데모를 끝낸 뒤 남은 미끼 프로세스 0개, 8080 과 9000 과 9101 과 9102 에 LISTENING 0줄.
- 고정 사례(`demo/fixed_cases.json`), 추가 사례의 기대값, 판정 코드(`demo/run_extra.py`)는 바꾸지 않았다. 다만 이 문서의 수집 스크립트(`request_target_parity.py`)는 #20 머지를 반영해 내부 경로의 기준을 바꿨다. 사유는 위 "입력" 절에 적었다.

## 관찰

1. **원인은 프록시가 요청 줄을 URL 로 다시 해석한 것이다.** 고치기 전 `forward()` 는 `f"http://{config.HOST}:{port}{path}"` 로 주소를 이어 붙여 urllib 에 넘겼다. 깨지는 방식은 요청 줄에 따라 둘이다.

    - 절대 URI: `http://127.0.0.1:9000http://127.0.0.1:9101/__health` 가 되고, `urlsplit` 이 netloc 을 `127.0.0.1:9000http:` 로 끊는다. 포트 자리가 비어 80 으로 떨어지고 `127.0.0.1:9000http` 가 호스트 이름이 되어, 이름을 찾다가 `urllib.error.URLError: <urlopen error [Errno 11001] getaddrinfo failed>` 가 난다 (errno 는 Windows 기준).
    - 슬래시로 시작하지 않는 경로: `http://127.0.0.1:9000nope` 가 되어 포트 자리가 `9000nope` 가 되고 `http.client.InvalidURL: nonnumeric port: '9000nope'` 가 난다.

    `HTTPError` 가 `URLError` 의 하위 클래스라서 `except urllib.error.HTTPError` 는 위 두 예외를 잡지 못한다. 그래서 `_handle()` 밖으로 빠져나가고 응답 없이 연결이 끊겼다.

2. **연결이 끊기는 것 자체가 기만 실패다.** 같은 요청을 타깃에 직접 보내면 404 가 오는데 프록시는 끊었다. 미끼인지 타깃인지는 드러나지 않지만, 앞에 무언가 끼어 있다는 사실이 드러난다. 원논문 7절은 응답 시간, 컨테이너 환경 같은 탐지 경로를 다루는데, 이쪽은 프록시를 쓰지 않는 원논문에는 없는 축소 구현 문제다.

3. **조각(#)이 붙은 경로는 반대 방향으로 샜다.** urllib 은 `/heartbeat#x` 에서 `#x` 를 떼고 `/heartbeat` 를 보낸다. 그래서 프록시는 200 을 주는데 타깃 직접은 404 다. 끊기지 않으니 수정 전 기록에서는 안 보였고, 이번에 사례를 늘려서 찾았다.

4. **고친 방식은 요청 줄을 그대로 중계하는 것이다.** `http.client` 는 `putrequest` 에 넘긴 경로를 요청 줄에 손대지 않고 싣는다. 절대 URI 도 조각이 붙은 경로도 타깃이 받은 그대로 보게 되고, 타깃이 라우팅하지 못해 주는 404 가 그대로 돌아온다. 프록시가 스스로 404 를 만들어 내는 것이 아니라 타깃의 404 를 중계하는 것이라, 타깃의 라우팅이 바뀌어도 자동으로 따라간다.

5. **중계가 아예 불가능한 요청 줄에는 프록시가 타깃과 같은 404 를 만들어 답한다.** `http.client` 는 요청 줄을 ASCII 로 인코딩하므로 비ASCII 경로는 중계할 수 없다. 타깃에 직접 보내면 어떤 비ASCII 경로든 404 `not found` 였으므로(`GET /한`, `GET /files/한.txt`, `GET /\xff\xfe` 로 확인) 같은 응답을 돌려주고, 사유는 `defender.jsonl` 에 `relay_fail` 로 남긴다. 어떤 이유로든 연결을 끊지 않는 것이 목적이다.

6. **`//__health` 는 #20 머지 뒤로 타깃 직접과 달라졌다.** 프록시와 타깃이 둘 다 `BaseHTTPRequestHandler` 라, 앞의 `//` 를 `/` 하나로 줄이는 같은 처리(CPython `http/server.py` 의 `parse_request`)를 거친다. 그래서 양쪽 다 `/__health` 를 보게 되는데, 프록시는 #20 의 `/__` 차단에 걸려 404 를 주고 타깃은 미끼 여부를 담은 200 을 준다. #20 이 의도한 동작이다. 공격자는 타깃 포트에 닿지 못해야 하고 거기가 열려 있는 것은 따로 C10(Issue #24)으로 잡혀 있으므로, 이 차이는 기만 실패가 아니다. 처음 올린 스크립트가 이것 때문에 "13건 중 1건 어김"이 되어, 내부 경로의 기준을 없는 경로의 404 로 고쳤다.

7. **#20 차단이 C9 의 한 사례를 가린다.** `/__health#x` 는 #20 전에는 프록시만 200 을 주는 C9 사례였다. 지금은 `/__` 차단이 `forward()` 보다 먼저 걸려서, C9 를 고치지 않은 상태에서도 기준과 같은 404 가 나온다. 그래서 수정 전 수치가 처음 재던 6건에서 5건으로 줄었다. 조각(#) 때문에 응답이 갈리는 현상 자체는 내부 경로가 아닌 `/heartbeat#x` 에 그대로 남아 있다.

8. **같이 안 고친 곳.** `_fork()` 와 미끼 재전송에서 부르는 `forward()` 는 감싸지 않았다. 이 두 곳은 요청 줄 때문이 아니라 미끼가 죽었을 때만 실패하고, 그때 공격자에게 무엇을 돌려주는 것이 맞는지는 풀 고갈(C6) 과 함께 봐야 한다. `/__hp/fork` 경로 자체는 C8(Issue #22) 에서 제어 포트로 옮기는 중이라 그 작업과 겹친다.

9. **타깃이 죽어 있을 때도 404 가 나간다.** 5번의 `relay_fail` 처리는 중계 실패 사유를 가리지 않으므로, 타깃이 내려가 있으면 404 를 준다. 공격자에게는 끊는 것보다 나은 응답이지만, 방어자가 장애를 응답만 보고 알 수 없다. `defender.jsonl` 의 `relay_fail` 로 구분한다. `demo/run_demo.py` 는 타깃을 먼저 기동 확인한 뒤 프록시를 확인하므로(`wait_up` 호출 순서) 이 때문에 판정이 흔들리지는 않는다.
