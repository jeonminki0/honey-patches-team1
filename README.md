# Mini RedHerring — Honey-Patch 축소 구현 (SSS 1팀)

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
python server/app.py --mode honeypatched --role decoy  --port 9101 &
python server/app.py --mode honeypatched --role decoy  --port 9102 &
python proxy/proxy.py &
python demo/client.py --session attacker-1 --payload hi --length 64
```

## 구조

```
honeypatch/config.py   포트, 시드 사용자(진짜 비밀)
honeypatch/hp.py       hp_init / hp_fork / hp_skip   (논문 §3, Listing 2·3)
honeypatch/redact.py   같은 길이·형식의 가짜 값으로 비밀 치환 (논문 §4.1)
server/app.py          취약 서버 /heartbeat, --mode unpatched|patched|honeypatched, --role target|decoy
proxy/proxy.py         리버스 프록시 + 미끼 풀(acquire) + 세션 고정 (논문 §3)
demo/fixed_cases.json  11주차 고정 검증 사례 3종 (수정 금지)
demo/run_demo.py       3모드 × 3사례 실행, 비교표·판정
demo/client.py         수동 요청 CLI
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
| LXC 컨테이너 풀 + overlayfs 재생성 | 로컬 프로세스 2개 풀 (재활용 미구현) |

## 진행 현황 / TODO

- [x] 3모드 서버, hp 라이브러리, redaction, 프록시 fork·세션 고정, 고정 사례 자동 판정
- [ ] 미끼 release·재활용 (destroy → clone → start), 세션 타임아웃
- [ ] 미끼 허니파일, 공격자 행위 로그
- [ ] (선택) Docker 컨테이너로 미끼 격리, CRIU 시도
- [ ] 14주차 변수 실험: redaction 켬/끔에 따른 공격자 응답 시간

## 재현 기록

| 팀원 | OS | Python | 결과 | 메모 |
|---|---|---|---|---|
| | | | | |
