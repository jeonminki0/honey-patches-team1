# Mini RedHerring: Honey-Patch 축소 구현

> **팀원은 작업 전에 [CONTRIBUTING.md](CONTRIBUTING.md)(팀 작업 규칙)를 먼저 읽어 주세요.**

- 논문: *From Patches to Honey-Patches: Lightweight Attacker Misdirection, Deception, and Disinformation* (Araujo et al., ACM CCS 2014)
- 팀: 소프트웨어및시스템보안 1팀 (전민기, 김영석, 우지민, 이현우, 김태우)

일반 패치는 공격 입력을 거부해서 "이 서버는 패치됨"을 공격자에게 알려 준다. 이 저장소는 같은 탐지 조건에서 거부 대신 공격자 세션을 **비밀 요소가 제거된 미끼(decoy)** 로 옮겨 공격이 성공한 것처럼 보이게 하는 허니패치의 핵심 흐름을, Heartbleed 구조의 취약 서버와 리버스 프록시·미끼 풀로 축소 구현한 것이다.

## 실행 환경

- OS: Linux (Ubuntu 24.04 / WSL2), Windows 11 (네이티브), macOS (Apple Silicon)에서 확인 (아래 "재현 기록" 참고). Windows는 종료 후 미끼 프로세스가 남는 문제가 있음 (아래 "알려진 문제" 참고)
- 언어·버전: Python 3.8 이상 (3.12·3.13·3.15에서 확인)
- 필요한 패키지: 없음 (표준 라이브러리만 사용)
- 사용 포트: 8080(프록시), 9000(타깃), 9101·9102(미끼). 바꾸려면 `honeypatch/config.py` 수정

## 설치

```bash
git clone https://github.com/jeonminki0/honey-patches-team1.git
cd honey-patches-team1
```

별도 설치는 없다. 명령어는 환경에 따라 `python`(Windows는 `py`, macOS는 `python3`)으로 바꿔 쓴다.

## 실행

**한 줄 실행**: 3모드(미패치·패치·허니패치) × 검증 사례 3종을 같은 입력으로 실행하고 비교표와 판정을 출력한다.

```bash
python3 demo/run_demo.py
```

- 마지막 줄에 `15/15 통과`가 나오면 정상
- 결과 파일: `results/compare.md`(비교표·PASS/FAIL), `results/raw_results.json`, `logs/defender.jsonl`(방어자 내부 로그), `logs/attacker.jsonl`(공격자 행위 로그)

**수동 실행**: 공격자·정상 사용자 입장에서 요청을 하나씩 보내 본다. 터미널을 따로 띄워 각각 실행한다.

```bash
# 터미널 1: 타깃 서버 (모드: unpatched | patched | honeypatched)
python3 server/app.py --mode honeypatched --role target --port 9000
# 터미널 2: 프록시 (미끼 9101·9102를 자동으로 띄움)
python3 proxy/proxy.py
# 터미널 3: 방어자 로그 보기 (PowerShell: Get-Content logs\defender.jsonl -Wait)
tail -f logs/defender.jsonl
# 터미널 4: 요청 보내기
python3 demo/client.py --session user-a     --payload hello --length 5    # 정상
python3 demo/client.py --session attacker-1 --payload hi    --length 64   # 공격 → 미끼로 전환
python3 demo/client.py --session attacker-1 --payload ping  --length 4    # 같은 공격자 → 계속 미끼
curl -H "X-Session-Id: attacker-1" http://127.0.0.1:8080/files/users.csv  # 미끼의 가짜 파일
```

- 미끼는 프록시가 자동으로 띄운다. 미끼를 따로 띄우면 포트가 겹친다.
- 끝낼 때는 터미널 1·2를 **Ctrl+C**로 끈다 (강제 종료하면 미끼 프로세스가 남는다).

**미끼 풀 단위 확인 스크립트** (각각 따로 실행, 포트가 비어 있어야 함)

```bash
python3 tests/decoy_pool/check_release.py   # release → 재생성 → 다시 acquire
python3 tests/decoy_pool/check_files.py     # 허니파일 제공, 경로 조작 차단
python3 tests/decoy_pool/check_timeout.py   # DECOY_TIMEOUT 후 자동 release (약 1분 소요)
```

## 검증 사례

11주차에 고정한 사례이며 수정하지 않는다 (`demo/fixed_cases.json`). 요청은 모두 `POST /heartbeat`.

| 구분 | 입력 | 기대 결과 |
| --- | --- | --- |
| 정상 | `{"payload":"hello","length":5}` (일반 사용자 세션) | 응답 200, 본문 "hello"(5바이트). fork 0회(로그), 프록시는 계속 타깃으로 전달. 미패치·패치·허니패치 세 버전 응답이 동일. |
| 위반 | `{"payload":"hi","length":64}` (선언 길이 > 실제 길이) | 미패치: 200·64바이트, 실제 비밀(다른 사용자 토큰) 포함. 패치: 거부(400). 허니패치: fork 1회 후 미끼가 미패치와 같은 형식의 200·64바이트로 응답하되 실제 비밀 문자열 0건(같은 길이 가짜 값). 같은 세션의 다음 요청도 미끼로 가고, 동시 접속한 정상 사용자 요청은 타깃에서 정상 처리. |
| 경계 | `{"payload":"hello","length":6}` (실제 길이 + 1) | 1바이트 초과도 위반으로 판정: fork 1회, 미끼가 6바이트 응답(6번째 바이트는 가짜 데이터), 실제 비밀 0건. (바로 아래 경계 length=5는 정상 사례와 같이 fork 0회) |

**판정 기준 (기대 결과를 코드·출력값으로 구체화)**

| 항목 | 측정 방법 |
|---|---|
| 비밀 노출 수 | 응답 본문에 `config.SEED_USERS`의 token·user·ip 문자열이 나타난 개수 |
| fork 수 | `logs/defender.jsonl`의 `fork_ok` 이벤트 수 |
| 라우팅 | `logs/defender.jsonl`의 `route` 이벤트 (target / decoy) |
| 경계 6번째 바이트 | 진짜 힙 첫 바이트(alice 토큰 첫 글자)와 다른지 |

## 원논문과의 차이

| 원논문 | 이 구현 |
|---|---|
| Apache·Lighttpd·Nginx (C) | Python 표준 라이브러리 HTTP 서버, Heartbleed 구조를 흉내 낸 `/heartbeat` |
| CRIU로 프로세스 전체 체크포인트·복원 | 세션 상태(JSON)만 직렬화·복원 |
| 체크포인트 중 구조체 메모리 redaction | 직렬화할 때 세션 레코드 redaction (같은 길이·형식의 가짜 값) |
| TCP repair로 연결 이전 | 상태 복원 후 요청 재전송(replay). 공격 요청이 타깃과 미끼에서 두 번 처리됨 |
| LXC 컨테이너 풀 + overlayfs 재생성 | 로컬 프로세스 2개 풀. release할 때 프로세스를 종료하고 같은 포트로 다시 띄움(빈 상태로 시작) |
| 미끼 컨테이너 수명 정책 | 고정 세션이 `DECOY_TIMEOUT`(30초) 동안 요청이 없으면 자동 release |
| 미끼 파일시스템에 허니파일 배치 | `GET /files/<이름>`으로 `decoy_template/` 파일 제공 (형식은 같고 값만 가짜) |
| 미끼 안에서 공격자 행위 감시·수집 | 프록시가 미끼로 간 요청, 위반 입력, 형식 오류 요청만 `logs/attacker.jsonl`에 기록 (모드, 입력·응답 길이(바이트), 상태, 진짜 비밀 노출 개수). 요청 본문과 비밀 값은 저장하지 않고, `/__` 내부 경로는 기록하지 않음 |

## 참고 자료

- 원논문: F. Araujo, K. W. Hamlen, S. Biedermann, S. Katzenbeisser. *From Patches to Honey-Patches.* ACM CCS 2014. https://doi.org/10.1145/2660267.2660329
- 참고한 코드·라이브러리: Python 표준 라이브러리(`http.server`, `urllib`, `subprocess`, `threading`). 원저자 코드는 공개된 것을 찾지 못해 참고하지 않음
- AI 활용: Claude(설계·기본 틀 작성, Claude Code CLI로 미끼 풀 구현·확인 스크립트·문서 반영), ChatGPT(요약·설명 교차 검토). 저장소의 `CLAUDE.md`에 AI 작업 규칙(표준 라이브러리만 사용, 고정 사례·판정 로직 수정 금지, 단계마다 실행 확인 후 커밋)을 두었고, AI가 보고한 결과는 팀원이 직접 재실행해 확인함

---

## 부록

### 구조

```
honeypatch/config.py   포트, 시드 사용자(진짜 비밀), DECOY_TIMEOUT
honeypatch/hp.py       hp_init / hp_fork / hp_skip   (논문 §3, Listing 2·3)
honeypatch/redact.py   같은 길이·형식의 가짜 값으로 비밀 치환 (논문 §4.1)
server/app.py          취약 서버 /heartbeat, GET /files/<이름>, --mode unpatched|patched|honeypatched, --role target|decoy
proxy/proxy.py         리버스 프록시 + 세션 고정 + 세션 타임아웃 감시 + 공격자 행위 로그 (논문 §3)
proxy/pool.py          미끼 풀: 미끼 프로세스 기동·acquire·release(destroy → clone → start)
data/                  타깃이 주는 진짜 파일 (config.txt, users.csv)
decoy_template/        미끼가 주는 같은 형식의 가짜 파일 (허니파일, 실제 비밀 없음)
demo/fixed_cases.json  11주차 고정 검증 사례 3종 (수정 금지)
demo/run_demo.py       3모드 × 3사례 실행, 비교표·판정
demo/client.py         수동 요청 CLI
tests/decoy_pool/      미끼 풀 단위 확인 스크립트 (release, 타임아웃, 허니파일)
logs/defender.jsonl    방어자 내부 로그: fork·route·release·timeout (실행 시 생성, git 제외)
logs/attacker.jsonl    공격자 행위 로그: 미끼로 간 요청·위반 입력·형식 오류 요청 (실행 시 생성, git 제외)
results/               compare.md(비교표·판정), raw_results.json (실행 시 생성, git 제외)
```

### 동작 흐름 (허니패치 모드, 위반 입력)

1. 클라이언트 → 프록시 → 타깃 `/heartbeat` (`length > len(payload)`, 원래 패치의 탐지 조건)
2. 타깃 `hp_fork()`: 세션 상태 직렬화 → 공격자 외 사용자 비밀 redaction → 프록시 `/__hp/fork`
3. 프록시: 미끼 acquire → 미끼 `/__hp/restore`로 상태 복원 → 세션을 미끼에 고정
4. 타깃은 `X-HP-Forked` 표시만 돌려줌 → 프록시가 같은 요청을 미끼로 재전송
5. 미끼에서는 `hp_skip()`이 거부를 건너뛰어 취약 코드 실행 → 가짜 비밀이 담긴 응답
6. fork 실패(미끼 풀 고갈 등) 시 타깃에서 `hp_skip()`이 거부(400)를 실행 → 일반 패치와 동일
7. 고정 세션이 `DECOY_TIMEOUT` 동안 조용하면 미끼를 release하고 재생성 → 이후 요청은 다시 타깃으로

### 진행 현황 / TODO

- [x] 3모드 서버, hp 라이브러리, redaction, 프록시 fork·세션 고정, 고정 사례 자동 판정
- [x] 미끼 release·재생성, 세션 타임아웃
- [x] 미끼 허니파일
- [x] 공격자 행위 로그 (프록시에서 기록, `logs/attacker.jsonl`)
- [ ] `run_demo.py` 시작 전 포트 사용 여부 확인
- [ ] Windows 종료 후 미끼 프로세스 잔류 수정
- [ ] 외부 요청의 내부 경로(`/__*`) 차단 (`/__health` 미끼 정체 노출, `/__hp/restore` 외부 호출)
- [ ] (선택) Docker 컨테이너로 미끼 격리, CRIU 시도
- [ ] 14주차 변수 실험: redaction 켬/끔에 따른 공격자 응답 시간

### 알려진 문제

- **Windows에서 미끼 프로세스가 남음 (재현됨, Windows 11 / Python 3.13)**: Windows의 `terminate()`는 종료 신호 없이 프록시를 바로 죽이므로, 프록시가 띄운 미끼가 정리되지 않는다. `run_demo.py` 한 번 실행 후 미끼 6개가 남아 9101·9102 포트를 점유했다. 다음 실행 전에 PowerShell에서 정리한다.

  ```powershell
  # 9101·9102를 점유한 프로세스 종료
  Get-NetTCPConnection -LocalPort 9101,9102 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
  # 포트를 잡지 못한 채 남은 미끼까지 정리
  Get-CimInstance Win32_Process -Filter "Name LIKE 'python%' OR Name LIKE 'py.exe'" |
    Where-Object { $_.CommandLine -match 'server[\\/]app\.py.*--role decoy' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  ```
  ※ 위 정리 명령은 Windows에서 아직 실행 확인 전

  cmd에서는 `netstat -ano | findstr :9101`로 PID를 확인한 뒤 `taskkill /PID <PID> /F`로 종료한다.
- **타임아웃 직후 요청이 끊길 수 있음**: 타임아웃이 되면 세션 고정을 먼저 풀고 미끼를 재생성한다. 그 순간 그 미끼로 가던 요청이 있으면 연결이 끊길 수 있다. 이후 요청은 정상적으로 타깃으로 간다.
- **이전 실행의 프록시가 남아 있으면 결과가 틀어짐**: `run_demo.py`는 포트가 이미 쓰이고 있어도 응답만 오면 기동된 것으로 본다. 남은 프록시(이전 세션 고정 상태 포함)와 통신하면 FAIL이 나온다(실제로 12/15 발생). 데모 전에 `proxy.py`·`app.py` 프로세스가 남아 있지 않은지 확인하고, 프록시는 일반 종료(Ctrl+C, `kill`)로 끈다.
- **`logs/attacker.jsonl`은 실행마다 누적됨**: `run_demo.py`는 `defender.jsonl`만 새로 만든다. 기록의 `mode`로 모드는 구분되지만 어느 실행의 기록인지는 `t`(시각)로 구분해야 한다.
- **내부 제어 경로가 외부에 열려 있음 (13주차 수정 예정)**: 미끼에 고정된 공격자가 `GET /__health`를 보내면 `decoy:honeypatched`가 돌아와 미끼임이 드러난다. 또 프록시가 외부에서 온 `/__hp/restore`를 미끼로 그대로 넘겨 공격자가 미끼 상태를 덮어쓸 수 있다.

### 재현 기록

| 팀원 | OS | Python | 결과 | 메모 |
|---|---|---|---|---|
| 우지민 | Ubuntu (WSL2) | 3.12.3 | 15/15 통과 | 작성자 환경 |
| 김태우 | Ubuntu 24.04 (WSL2) | 3.12.3 | 15/15 통과 | 실행 후 잔류 프로세스·포트 점유 없음 |
| 김영석 | Windows 11 (네이티브) | 3.13.14 | 15/15 통과 | 종료 후 미끼 6개 잔류(9101, 9102 점유). PID 지정 종료 필요 |
| 이현우 | macOS (Apple Silicon) | 3.15.2 | 15/15 통과 | 확인 스크립트 3종 통과(6/6, 5/5, 6/6), README 수동 실행 정상, 종료 후 잔류 프로세스·포트 점유 없음 |
