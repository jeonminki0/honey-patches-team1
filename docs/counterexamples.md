# 반례 기록 (13주차)

기대와 다르게 동작하는 입력을 기록한다. **기대 결과는 실행 전에 적고**, 실제 결과는 실행 후 채운다.
분류는 셋 중 하나다: **구현 버그**(우리 코드가 틀림) / **명세상 미지원**(축소 구현에서 일부러 다루지 않은 범위) / **원논문 한계**(원논문 방식 자체의 한계).

- 재현: `python3 demo/run_extra.py --case <사례 id>` (사례 정의는 `demo/extra_cases/`)
- 수정 전 증거: `evidence/before/`, 수정 후 증거: `evidence/after/` (같은 입력으로)
- 아래 C1~C6은 초안이다. "판단 근거"의 원논문 절 번호는 원문과 대조해 확정한다.

| 번호 | 입력 | 기대 결과(실행 전) | 실제 결과 | 분류 | 판단 근거(원논문 절) | 처리 | 수정 전·후 |
|---|---|---|---|---|---|---|---|
| C1 | `POST /heartbeat` `{"payload":"hello","length":-1}`, 세 모드 (`server.json` `C1-negative-length`) | 미패치: 200·비밀 노출(보호 전이므로 정상). 패치: 400·비밀 0. 허니패치: fork 1·미끼 응답·비밀 0 | 세 모드 모두 200·107B·**진짜 비밀 6건**. fork 0, `attacker.jsonl` 기록 없음 | 구현 버그 | 원논문 대상(OpenSSL Heartbleed, Listing 1·2)은 길이를 부호 없는 16비트로 읽어 음수가 없다. 패치 조건 `length > len(payload)`만 옮기고 파이썬 슬라이스 `[:-1]`의 의미를 고려하지 않아 생긴 축소 구현 버그 | 미정 (담당 전민기) | 전: `evidence/before/a_negative_length.md`, run_extra FAIL(patched·honeypatched) / 후: - |
| C2 | 허니패치. 공격(hi/64) 후 같은 세션 `GET /__health` (`proxy.json` `C2-health-fingerprint`) | 미끼에 고정된 공격자도 정상 사용자와 같은 응답 | 정상 사용자 `target:honeypatched`, 공격자 **`decoy:honeypatched`** → 미끼임이 드러남 | 구현 버그 | 허니패치의 목표는 공격자가 미끼를 구분하지 못하게 하는 것(§3 구조, 절 번호 확인 필요). 내부 상태 확인용 경로를 외부에 그대로 전달한 구현 문제 | 미정 (담당 김영석) | 전: `evidence/before/c_health_fingerprint.md`, run_extra FAIL / 후: - |
| C3 | 허니패치. 공격 후 같은 세션 `POST /__hp/restore` `{"state":{"sessions":[]}}`, 다시 hi/64 (`proxy.json` `C3-restore-external`) | 외부 restore는 미끼에 도달하지 않음(404). 이후 공격 응답 64B 유지 | restore **200 `restored`**, 이후 응답 64B → **38B**(`hi0000000000000000\|attacker\|127.0.0.1;`) | 구현 버그 | 원논문에서 체크포인트·복원은 방어자 내부(LXC 컨트롤러)가 수행한다(§3, 절 번호 확인 필요). 이 구현은 같은 HTTP 포트로 restore를 받고 프록시가 외부 경로를 거르지 않음 | 미정 (담당 김영석) | 전: `evidence/before/d_restore_overwrite.md`, run_extra FAIL / 후: - |
| C4 | 미패치. 타깃 직접 `{"payload":"a","length":"abc"}`(세션 `ghost-1`) 후 힙 읽기 (`server.json` `C4-malformed-adds-session`) | 형식이 깨진 요청(400)은 세션 테이블을 바꾸지 않음 | 400이지만 **`ghost-1` 레코드가 테이블에 추가됨**. 공격자 세션도 fork 뒤 타깃에 남음 | 구현 버그 | 원논문과 무관한 축소 구현 문제(`ensure_session()`이 입력 해석 전에 실행됨). 세션 ID만 바꿔 반복하면 테이블이 계속 커짐 | 미정 (담당 전민기) | 전: `evidence/before/e_target_session_table.md`, run_extra FAIL / 후: - |
| C5 | 허니패치. 공격자가 `X-Session-Id: user-normal`로 공격 → 진짜 user-normal이 `GET /files/users.csv` (`redact.json` `C5-session-spoofing`) | 진짜 user-normal은 타깃으로 가서 진짜 파일을 받음 | 진짜 사용자가 **미끼에 고정**되어 가짜 파일(`s-marta`)을 받고, 그 요청이 공격자 행위로 기록됨 | 명세상 미지원 | 원논문은 공격자의 TCP 연결 자체를 미끼로 옮긴다(§3, 절 번호 확인 필요). 연결이 곧 세션이라 다른 사용자가 끼어들 수 없다. 이 구현은 클라이언트가 정하는 헤더 값으로 세션을 식별한다(README "원논문과의 차이": TCP repair → replay) | 미정 (담당 이현우) | 전: `evidence/before/f_session_spoofing.md`, run_extra FAIL / 후: - |
| C6 | 허니패치. 서로 다른 세션 3개(attacker-1·2·3)로 연속 공격 hi/64 (사례 파일 미작성) | 미정. 팀 논의 필요 (예: 세 번째도 미끼 응답, 또는 고갈 시 동작을 명세로 정함) | 미끼 풀 2개가 소진되어 attacker-3은 `fork_fail` → **400**(일반 패치와 같은 응답). 공격 요청 하나가 미끼 하나를 차지하므로, 세션 ID만 바꿔 반복하면 이후 공격자는 모두 허니패치 대신 거부를 받음 | 원논문 한계 | 공격마다 미끼 컨테이너를 하나씩 쓰는 구조의 자원 한계(§7). C5처럼 세션 ID를 마음대로 만들 수 있어 이 구현에서는 더 쉽게 고갈됨 | 미정 (담당 우지민) | 전: 12주차 PR #5 재리뷰 실행 결과(`defender.jsonl`의 `fork_fail ... decoy pool empty`), `evidence/before/`에는 아직 없음 / 후: - |
