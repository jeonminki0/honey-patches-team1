# g. C7: 프록시가 강제 종료되면 미끼 프로세스가 남음 (Issue #16)

- 기준 커밋: `5d136e4` (main, 소스 수정 없이 실행) · 실행 환경: Ubuntu (WSL2), Python 3.12.3
- 확인 스크립트: [`tests/decoy_pool/check_orphan.py`](../../tests/decoy_pool/check_orphan.py)

## 입력
1. 타깃(`--mode honeypatched --role target`)과 프록시(`proxy/proxy.py`)를 띄운다. 미끼 2개(9101·9102)는 프록시가 `proxy/pool.py`로 띄운다.
2. 프록시를 **정리 코드가 실행되지 않는 방식으로** 강제 종료한다.
   - POSIX: `SIGKILL` (이번 실행)
   - Windows: `Popen.terminate()` (= TerminateProcess. `run_demo.py`가 프록시를 끄는 방식과 같다)
3. 2초 뒤 미끼 포트 점유 여부와 미끼 프로세스(`--role decoy`)가 남았는지 확인한다.

## 실행 명령
```bash
python3 tests/decoy_pool/check_orphan.py    # FAIL이면 종료 코드 1. 끝에 남은 미끼는 스크립트가 정리
```

## 출력
```
기동: 타깃 pid 15259, 프록시 pid 15260
강제 종료 전 미끼 관련 프로세스 2개:
   15261  /usr/bin/python3 .../server/app.py --mode honeypatched --role decoy --port 9101
   15262  /usr/bin/python3 .../server/app.py --mode honeypatched --role decoy --port 9102
강제 종료 전 미끼 포트 점유: {9101: True, 9102: True}
프록시 강제 종료: SIGKILL, 종료 코드 -9
2초 뒤 미끼 포트 점유: [9101, 9102]
2초 뒤 남은 미끼 관련 프로세스 2개:
   15261  /usr/bin/python3 .../server/app.py --mode honeypatched --role decoy --port 9101
   15262  /usr/bin/python3 .../server/app.py --mode honeypatched --role decoy --port 9102
[FAIL] 프록시 강제 종료 후 미끼 잔류 없음
정리: 남은 미끼 관련 프로세스 2개 강제 종료, 정리 후 0개, 포트 점유 없음
```
(종료 코드 1. 경로의 저장소 앞부분은 `...`로 줄임)

| 확인 항목 | 기대(실행 전) | 실제 | 판정 |
|---|---|---|---|
| 프록시 강제 종료 2초 뒤 9101·9102 점유 | 없음 | 9101, 9102 점유 | **FAIL** |
| 프록시 강제 종료 2초 뒤 미끼 프로세스 | 0개 | 2개 (강제 종료 전과 같은 pid) | **FAIL** |

## 관찰
1. 프록시가 죽어도 미끼 2개가 **같은 pid로 그대로 살아 있고 포트를 계속 점유**한다. 미끼는 프록시의 자식이지만, 부모가 죽었다고 자식이 같이 죽지는 않는다.
2. 원인(코드): 미끼 정리는 프록시가 스스로 정리할 기회가 있을 때만 일어난다. SIGTERM 핸들러(`proxy/proxy.py` 188행)가 `sys.exit(0)`을 일으키고, `finally: pool.stop_all()`(191~192행)이 미끼마다 `terminate()`를 보낸다. SIGKILL이나 Windows의 `terminate()`(TerminateProcess)는 핸들러와 `finally`를 실행하지 않는다. 미끼 쪽(`server/app.py`)에도 부모가 사라진 것을 알아챌 방법이 없다.
3. **Windows에서는 평소 실행만으로 재현된다.** `demo/run_demo.py`는 모드마다 `p.terminate()`(72행)로 프록시를 끈다. POSIX에서는 SIGTERM이라 정리되지만, Windows에서는 TerminateProcess라 위와 같은 상황이 된다. README 재현 기록의 김영석 님 결과가 이를 보여 준다: **Windows 11 (네이티브), Python 3.13.14, 15/15 통과, "종료 후 미끼 6개 잔류(9101, 9102 점유). PID 지정 종료 필요"**. 3모드 × 미끼 2개 = 6개와 수가 맞는다.
4. 남은 미끼는 다음 실행을 방해한다. 새 프록시의 미끼는 포트를 잡지 못하고, `run_demo.py`의 `wait_up()`은 이전 미끼의 응답을 받아 정상으로 본다(README "알려진 문제"의 "이전 실행의 프록시가 남아 있으면 결과가 틀어짐"과 같은 구조). 남은 미끼에는 이전 실행에서 복원된 공격자 상태가 들어 있을 수 있다.
5. 고정 사례 3종과 추가 사례는 POSIX에서 이 문제를 드러내지 않는다. `run_demo.py` 15/15, `run_extra.py` 8/14(남은 FAIL은 C1~C5)로 C7과 무관하다.
