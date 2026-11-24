# 13주차 수정 전 증거 (반례 후보)

현재 코드를 수정하지 않고 그대로 실행한 결과다. 기준 코드는 `origin/main` `7e41b5c`, 실행 환경은 Ubuntu (WSL2), Python 3.12.3이다.
같은 시점의 `python3 demo/run_demo.py` 결과는 **15/15 통과**다. 고정 검증 사례 3종으로는 아래 문제가 드러나지 않는다.

재현 명령: `python3 evidence/before/collect.py` (원자료는 `raw.json`에 다시 기록됨. 가짜 값은 실행마다 바뀜)

| 사례 | 입력 요약 | 결과 | 진짜 비밀 노출 | attacker.jsonl 기록 |
|---|---|---|---|---|
| [a](a_negative_length.md) | `length: -1`, 세 모드 | **세 모드 모두 200·107B, 패치·허니패치 우회** | **6건** (세 모드 모두) | 없음 |
| [b](b_zero_length.md) | `length: 0`, 세 모드 | 200·0B (대조군, 문제 없음) | 0 | 없음 |
| [c](c_health_fingerprint.md) | 공격 후 같은 세션 `GET /__health` | **`decoy:honeypatched` 응답으로 미끼임이 드러남** | 0 | 없음 (`/__` 제외) |
| [d](d_restore_overwrite.md) | 공격 후 같은 세션 `POST /__hp/restore` | **미끼 상태가 덮어써지고 응답이 64B→38B로 바뀜** | 0 | restore는 없음 |
| [e](e_target_session_table.md) | 공격 전후 타깃 메모리 읽기 | 공격자 세션 레코드가 타깃에 남음. 지시한 hi/200 직접 요청은 fork되어 빈 응답 | 6건 (`length -1`로 읽음) | 없음 (타깃 직접) |
| [f](f_session_spoofing.md) | `X-Session-Id: user-normal` 사칭 공격 | **진짜 user-normal이 미끼에 고정되어 가짜 파일을 받음** | 0 | 진짜 사용자 요청이 공격자로 기록됨 |

12주차 리뷰에서 범위 밖 문제로 보고한 항목과의 관계는 다음과 같다.
- c는 "미끼 고정 공격자의 `/__health` 노출"을 실행으로 확인한 것이다.
- d는 "프록시가 외부 `/__hp/restore`를 미끼로 전달"을 처음 실행으로 확인한 것이다.
- a, e, f는 이번에 새로 확인한 문제다.
