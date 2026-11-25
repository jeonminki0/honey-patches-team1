# g. C7: 프록시가 강제 종료되면 미끼 프로세스가 남음 (Issue #16), 수정 후

- 기준 커밋: `fix/c7-decoy-orphan` 브랜치의 수정 커밋 (`proxy/decoy_launcher.py` 추가, `proxy/pool.py` 수정) · 실행 환경: Ubuntu (WSL2), Python 3.12.3
- 확인 스크립트: [`tests/decoy_pool/check_orphan.py`](../../tests/decoy_pool/check_orphan.py) · 수정 전: [`evidence/before/g_c7_decoy_orphan.md`](../before/g_c7_decoy_orphan.md)

## 입력
수정 전과 같다.
1. 타깃(`--mode honeypatched --role target`)과 프록시(`proxy/proxy.py`)를 띄운다. 미끼 2개(9101·9102)는 프록시가 `proxy/pool.py`로 띄운다.
2. 프록시를 **정리 코드가 실행되지 않는 방식으로** 강제 종료한다.
   - POSIX: `SIGKILL` (이번 실행)
   - Windows: `Popen.terminate()` (= TerminateProcess)
3. 2초 뒤 미끼 포트 점유 여부와 미끼 관련 프로세스(`--role decoy`, `decoy_launcher.py`)가 남았는지 확인한다.

## 실행 명령
```bash
python3 tests/decoy_pool/check_orphan.py    # FAIL이면 종료 코드 1. 끝에 남은 미끼는 스크립트가 정리
```

## 출력
```
기동: 타깃 pid 16526, 프록시 pid 16527
강제 종료 전 미끼 관련 프로세스 4개:
   16528  /usr/bin/python3 .../proxy/decoy_launcher.py --mode honeypatched --role decoy --port 9101
   16529  /usr/bin/python3 .../proxy/decoy_launcher.py --mode honeypatched --role decoy --port 9102
   16531  /usr/bin/python3 .../server/app.py --mode honeypatched --role decoy --port 9102
   16533  /usr/bin/python3 .../server/app.py --mode honeypatched --role decoy --port 9101
강제 종료 전 미끼 포트 점유: {9101: True, 9102: True}
프록시 강제 종료: SIGKILL, 종료 코드 -9
2초 뒤 미끼 포트 점유: 없음
2초 뒤 남은 미끼 관련 프로세스 0개:
[PASS] 프록시 강제 종료 후 미끼 잔류 없음
정리: 남은 미끼 관련 프로세스 0개 강제 종료, 정리 후 0개, 포트 점유 없음
```
(종료 코드 0. 경로의 저장소 앞부분은 `...`로 줄임)

| 확인 항목 | 기대(실행 전) | 수정 전 | 수정 후 | 판정 |
|---|---|---|---|---|
| 프록시 강제 종료 2초 뒤 9101·9102 점유 | 없음 | 9101, 9102 점유 | 없음 | PASS |
| 프록시 강제 종료 2초 뒤 미끼 관련 프로세스 | 0개 | 2개 | 0개 (launcher 2 + 미끼 2 모두 종료) | PASS |

같은 커밋에서 함께 확인한 결과:

| 명령 | 수정 전 | 수정 후 |
|---|---|---|
| `python3 demo/run_demo.py` | 15/15 | 15/15 |
| `python3 demo/run_extra.py` | 8/14 (FAIL: C1·C2·C3·C4·C5) | 8/14 (FAIL: C1·C2·C3·C4·C5, 변화 없음) |
| `tests/decoy_pool/check_release.py` / `check_files.py` / `check_timeout.py` | 6/6 · 5/5 · 6/6 | 6/6 · 5/5 · 6/6 |
| `defender.jsonl`의 `decoy_force_kill` (마지막 수단 사용 횟수) | (이벤트 없음) | 0건 |

## 관찰
1. 미끼가 `proxy → decoy_launcher.py → server/app.py` 구조로 뜬다. 강제 종료 전 미끼 관련 프로세스가 4개(launcher 2, 미끼 2)인 이유다.
2. 프록시가 SIGKILL로 죽으면 운영체제가 프록시가 쥐고 있던 파이프의 쓰기 쪽을 닫는다. launcher는 stdin에서 EOF를 받고 미끼를 `terminate()`한 뒤 끝난다. 2초 안에 4개 모두 끝났고 포트도 비었다.
3. 정상 경로도 같은 방식으로 정리된다. `pool.release()`와 `stop_all()`은 파이프를 닫고 기다리며, `STOP_TIMEOUT`(5초) 안에 안 끝날 때만 강제 종료한다(`decoy_force_kill` 로그). 이번 전체 실행(데모, 추가 사례, 확인 스크립트 4개)에서 강제 종료는 한 번도 쓰이지 않았다.
4. `release()`의 destroy → clone → start와 `release` 로그는 그대로다. 로그의 `old_pid`·`new_pid`는 이제 미끼 서버가 아니라 launcher의 pid다.
5. Windows 확인 결과는 아래 "Windows 확인" 절에 있다. `run_demo.py` 후 잔류는 0개로 확인됐고, `check_orphan.py` 판정은 재확인 대기다.
6. 마지막 수단(파이프를 닫아도 launcher가 끝나지 않는 경우)은 일부러 재현하지 않아 실행으로 확인하지 못했다. POSIX에서는 SIGTERM 후 세션 전체 SIGKILL, Windows에서는 `taskkill /T /F`다.

## Windows 확인 (김영석 님 실행, 결과 전달받음)

- 환경: Windows 11 (네이티브), Python 3.13.14, `fix/c7-decoy-orphan` 브랜치

| 확인 항목 | 수정 전 | 수정 후 | 판정 |
|---|---|---|---|
| `python demo\run_demo.py` | 15/15 | 15/15 | 유지 |
| `run_demo.py` 실행 후 남은 미끼 프로세스 | **6개** (README 재현 기록) | **0개** | PASS |
| 실행 후 9101·9102 LISTEN | 점유됨 | 없음 | PASS |
| `python tests\decoy_pool\check_orphan.py` | - | **판정 전에 중단**: `UnicodeDecodeError` (cp949) | 재확인 대기 |

- `check_orphan.py` 중단 원인: 프로세스 목록(PowerShell 출력)을 시스템 기본 인코딩(한국어 Windows는 cp949)으로 디코딩한다. 이때 미끼와 무관한 프로세스의 명령줄에 cp949로 디코딩할 수 없는 바이트가 있어 예외가 났다. **미끼 잔류 판정 이전 단계의 스크립트 문제이고, C7 수정 자체의 실패가 아니다.**
- 조치: `subprocess.run(..., universal_newlines=True, errors="replace")`로 바꿔, 디코딩할 수 없는 바이트는 대체 문자로 바뀌고 실행이 계속되게 했다. 찾는 문자열(`app.py`, `--role decoy`, `decoy_launcher.py`, 포트 번호)은 모두 ASCII라 판정에 영향이 없다.
- Linux에서 cp949 디코딩을 흉내 내 확인함: 0xff 바이트가 섞인 출력에서 `errors` 없이는 `UnicodeDecodeError: 'cp949' codec can't decode byte 0xff ... illegal multibyte sequence`, `errors="replace"`로는 디코딩에 성공하고 미끼 줄도 인식했다.
- **남은 확인:** Windows에서 `python tests\decoy_pool\check_orphan.py`를 다시 실행해 `[PASS]`와 종료 코드 0인지 확인 (김영석 님).
