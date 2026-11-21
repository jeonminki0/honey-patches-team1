# Mini RedHerring — Honey-Patch 축소 구현 (SSS 1팀)
> **팀원은 작업 전에 [CONTRIBUTING.md](CONTRIBUTING.md)(팀 작업 규칙)를 먼저 읽어 주세요.**
논문: *From Patches to Honey-Patches: Lightweight Attacker Misdirection, Deception, and Disinformation* (Araujo et al., ACM CCS 2014)

일반 패치는 공격 입력을 거부해 "이 서버는 패치됨"을 드러낸다. 허니패치는 같은 탐지 조건에서 거부 대신 공격자 세션을
**비밀이 제거된 미끼(decoy)** 로 옮겨, 공격이 성공한 것처럼 보이게 한다. 이 저장소는 그 핵심 흐름을 Python으로 축소 구현한 것이다.

## 실행 (한 줄)

```bash
python demo/run_demo.py
```

- 요구 사항: Python 3.8 이상, **외부 패키지 없음** (표준 라이브러리만 사용)
- 사용 포트: 8080(프록시), 9000(타깃), 9101·9102(미끼). 이미 쓰는 포트가 있으면 `honeypatch/config.py`에서 변경
- 결과: 터미널 출력 + `results/compare.md`(비교표, 기대 결과 PASS/FAIL), `results/raw_results.json`, `logs/defender.jsonl`(방어자 내부 로그)
- 확인 환경: Ubuntu 22.04 / Python 3.12  (다른 환경 재현 결과는 아래 표에 추가)

수동으로 요청을 보내 보고 싶다면 서버를 띄운 뒤:

```bash
python server/app.py --mode honeypatched --role target --port 9000 &
python proxy/proxy.py &
python demo/client.py --session attacker-1 --payload hi --length 64
```

- 미끼(9101·9102)는 프록시가 자동으로 띄운다 (`proxy/pool.py`). 미끼를 따로 띄우면 포트가 겹치므로 띄우지 않는다.
- 허니파일 확인: `curl -H "X-Session-Id: attacker-1" http://127.0.0.1:8080/files/users.csv`
  (fork 전·정상 사용자는 `data/` 진짜 파일, 미끼에 고정된 세션은 `decoy_template/` 가짜 파일)

미끼 풀 단위 확인 스크립트 (각각 따로 실행, 포트가 비어 있어야 함):

```bash
python tests/decoy_pool/check_release.py   # release → 재생성 → 다시 acquire
python tests/decoy_pool/check_timeout.py   # DECOY_TIMEOUT 후 자동 release (기본 30초 → 약 1분 소요)
python tests/decoy_pool/check_files.py     # 허니파일 제공, 경로 조작 차단
```

## 구조

```
honeypatch/config.py   포트, 시드 사용자(진짜 비밀)
honeypatch/hp.py       hp_init / hp_fork / hp_skip   (논문 §3, Listing 2·3)
honeypatch/redact.py   같은 길이·형식의 가짜 값으로 비밀 치환 (논문 §4.1)
server/app.py          취약 서버 /heartbeat, GET /files/<이름>, --mode unpatched|patched|honeypatched, --role target|decoy
proxy/proxy.py         리버스 프록시 + 세션 고정 + 세션 타임아웃 감시 (논문 §3)
proxy/pool.py          미끼 풀: 미끼 프로세스 기동·acquire·release(destroy → clone → start)
data/                  타깃이 주는 진짜 파일 (config.txt, users.csv)
decoy_template/        미끼가 주는 같은 형식의 가짜 파일 (허니파일, 실제 비밀 없음)
demo/fixed_cases.json  11주차 고정 검증 사례 3종 (수정 금지)
demo/run_demo.py       3모드 × 3사례 실행, 비교표·판정
demo/client.py         수동 요청 CLI
tests/decoy_pool/      미끼 풀 단위 확인 스크립트 (release, 타임아웃, 허니파일)
```

## 동작 흐름 (허니패치 모드, 위반 입력)

1. 클라이언트 → 프록시 → 타깃 `/heartbeat` (`length > len(payload)`, 원래 패치의 탐지 조건)
2. 타깃 `hp_fork()`: 세션 상태 직렬화 → 공격자 외 사용자 비밀 redaction → 프록시 `/__hp/fork`
3. 프록시: 미끼 acquire → 미끼 `/__hp/restore`로 상태 복원 → 세션을 미끼에 고정
4. 타깃은 `X-HP-Forked` 표시만 돌려줌 → 프록시가 같은 요청을 미끼로 재전송
5. 미끼에서는 `hp_skip()`이 거부를 건너뛰어 취약 코드 실행 → 가짜 비밀이 담긴 응답
6. fork 실패(미끼 풀 고갈 등) 시 타깃에서 `hp_skip()`이 거부(400)를 실행 → 일반 패치와 동일

## 판정 기준 (11주차 기대 결과의 구체화)

| 항목 | 측정 방법 |
|---|---|
| 비밀 노출 수 | 응답 본문에 `config.SEED_USERS`의 token·user·ip 문자열이 나타난 개수 |
| fork 수 | `logs/defender.jsonl`의 `fork_ok` 이벤트 수 |
| 라우팅 | `logs/defender.jsonl`의 `route` 이벤트(target / decoy) |
| 경계 사례 6번째 바이트 | 진짜 힙 첫 바이트(alice 토큰 첫 글자)와 다른지 |

## 원논문과의 차이

| 원논문 | 이 구현 |
|---|---|
| Apache·Lighttpd·Nginx (C) | Python 표준 라이브러리 HTTP 서버, Heartbleed 구조를 흉내 낸 `/heartbeat` |
| CRIU로 프로세스 전체 체크포인트·복원 | 세션 상태(JSON)만 직렬화·복원 |
| 체크포인트 중 구조체 메모리 redaction | 직렬화할 때 세션 레코드 redaction |
| TCP repair로 연결 이전 | 상태 복원 후 요청 재전송(replay) |
| LXC 컨테이너 풀 + overlayfs 재생성 | 로컬 프로세스 2개 풀. release할 때 프로세스를 종료하고 같은 포트로 다시 띄움(빈 상태로 시작) |
| 미끼 컨테이너 수명 정책 | 고정 세션이 `DECOY_TIMEOUT`초(기본 30) 동안 요청이 없으면 자동 release |
| 미끼 파일시스템에 허니파일 배치 | `GET /files/<이름>`으로 `decoy_template/` 파일 제공 (형식은 같고 값만 가짜) |

## 진행 현황 / TODO

- [x] 3모드 서버, hp 라이브러리, redaction, 프록시 fork·세션 고정, 고정 사례 자동 판정
- [x] 미끼 release·재활용 (destroy → clone → start), 세션 타임아웃
- [x] 미끼 허니파일
- [ ] 공격자 행위 로그
- [ ] (선택) Docker 컨테이너로 미끼 격리, CRIU 시도
- [ ] 14주차 변수 실험: redaction 켬/끔에 따른 공격자 응답 시간

## 알려진 문제

- **Windows에서 미끼 정리 미확인**: 프록시가 미끼 프로세스를 띄우고, 종료 신호(SIGTERM)를 받으면 함께 정리한다.
  Windows의 `terminate()`는 신호 없이 바로 프로세스를 죽이므로 미끼가 남아, 다음 실행 때 9101·9102 포트가 충돌할 수 있다.
  Linux(Ubuntu 22.04 / Python 3.12)에서만 확인했다. Windows에서 실행 후 미끼 프로세스가 남는지 확인 필요.
- **타임아웃 직후 요청이 끊길 수 있음**: 타임아웃이 되면 세션 고정을 먼저 풀고 미끼를 재생성한다.
  고정 해제 직전에 그 미끼로 가던 요청이 있으면, 재생성 중 프로세스가 종료되어 연결이 끊길 수 있다.
  고정 해제 이후 요청은 정상적으로 타깃으로 간다.
- **이전 실행의 프록시가 남아 있으면 결과가 틀어짐**: `run_demo.py`는 포트가 이미 쓰이고 있어도 응답만 오면 기동된 것으로 본다.
  수동 실행한 프록시를 끄지 않고 데모를 돌리면 남은 프록시(이전 세션 고정 상태 포함)와 통신해 FAIL이 나온다
  (실제로 12/15 발생). 데모 전에 `python proxy/proxy.py`, `server/app.py` 프로세스가 남아 있지 않은지 확인하고,
  프록시는 강제 종료(`kill -9`) 대신 일반 종료(`kill`, Ctrl+C)로 끈다(그래야 미끼도 함께 정리됨).

## 재현 기록

| 팀원 | OS | Python | 결과 | 메모 |
|---|---|---|---|---|
| | | | | |
