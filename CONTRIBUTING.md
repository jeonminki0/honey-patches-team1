# 팀 작업 규칙 (1팀 · Honey-Patch 구현)

> 작업을 시작하기 전에 이 문서를 꼭 읽어 주세요.
> 프로젝트 설명과 실행 방법은 [README.md](README.md)에 있습니다.

## 1. 처음 한 번만: 저장소 받기와 실행 확인

```bash
git clone https://github.com/jeonminki0/honey-patches-team1.git
cd honey-patches-team1
python demo/run_demo.py        # Windows는 py, macOS/Linux는 python3 일 수 있음
```

- 마지막 줄에 **`15/15 통과`** 가 나오면 정상입니다.
- 결과는 [README.md](README.md) 맨 아래 **"재현 기록"** 표에 한 줄 추가해 주세요 (이름, OS, Python 버전, 결과).
- 오류가 나면 코드를 고치지 말고, 오류 메시지를 그대로 팀 채팅방에 공유해 주세요.

## 2. 담당과 브랜치: Issue 하나에 브랜치 하나

| 담당 | 담당 파일 |
|---|---|
| 전민기 | `server/app.py`, `honeypatch/hp.py` |
| 김영석 | `proxy/proxy.py` |
| 우지민 | `proxy/pool.py`, `decoy_template/` |
| 이현우 | `honeypatch/redact.py` |
| 김태우 | `demo/`, `README.md` |

main에서 바로 작업하지 않습니다. **Issue 하나마다 브랜치를 하나** 만들어 작업하고, merge되면 그 브랜치는 지웁니다.

| 접두어 | 쓰는 경우 | 예시 |
|---|---|---|
| `fix/` | 반례·버그 수정 | `fix/negative-length` |
| `case/` | 추가 사례(`demo/extra_cases/`) 작성 | `case/proxy-internal-path` |
| `docs/` | 문서 | `docs/readme-week13` |

```bash
git switch main
git pull                                  # 항상 최신 main에서 시작
git switch -c fix/negative-length         # Issue에 맞는 브랜치 만들기
git push -u origin fix/negative-length    # 처음 한 번만
```

- 담당 파일 외의 파일을 고쳐야 하면, 먼저 해당 담당자에게 말해 주세요. 같은 파일을 동시에 고치면 충돌이 납니다.
- merge 후 정리: `git switch main && git pull && git branch -d fix/negative-length` (원격 브랜치는 GitHub PR 화면의 "Delete branch" 또는 `git push origin --delete fix/negative-length`)

## 3. 작업 흐름

```bash
git switch fix/negative-length    # Issue 브랜치에서
# ... 작업 ...
python demo/run_demo.py           # 고정 사례 15/15 확인
python demo/run_extra.py          # 추가 사례 결과 확인
git add .
git commit -m "fix: 음수 length 거부"
git push
```

- **한 번에 한 기능만** 바꾸고, 바꿀 때마다 실행해서 확인한 뒤 커밋합니다.
- 동작이 확인될 때마다 커밋해 두면, 나중에 문제가 생겼을 때 돌아갈 지점이 됩니다.

### 커밋 메시지 규칙

| 머리말 | 쓰는 경우 | 예시 |
|---|---|---|
| `feat:` | 기능 추가 | `feat: 미끼 release 추가` |
| `fix:` | 버그 수정 | `fix: 포트 사용 중일 때 종료 처리` |
| `test:` | 검증 사례·측정 | `test: 연속 공격 3회 사례 추가` |
| `docs:` | 문서 | `docs: 원논문 차이 표 갱신` |

## 4. main에 합치기 (Pull Request)

- **main에는 직접 push하지 않습니다.** GitHub에서 `내 브랜치 → main` 으로 Pull Request(PR)를 만들어 주세요.
- PR 올리기 전 체크:
  - [ ] 최신 main을 먼저 받아 충돌 해결: `git pull origin main`
  - [ ] `python demo/run_demo.py` 실행 결과 **15/15 통과**
  - [ ] `python demo/run_extra.py` 결과(통과 수, 남은 FAIL 목록)
  - [ ] PR 설명에 **무엇을 바꿨는지 + 실행 결과(통과 수)** 붙이기
  - [ ] PR 설명에 관련 Issue를 `Closes #번호`로 적기 (merge되면 Issue가 자동으로 닫힘)
- **다른 팀원 1명**이 확인하고 merge합니다. 본인 PR을 본인이 merge하지 않습니다.

## 5. 절대 하지 않을 것

- `demo/fixed_cases.json` 의 고정 검증 사례 3종을 수정하지 않습니다. (11주차 고정 규칙, 14주차까지 그대로 제출)
- 결과가 기대와 다르다고 판정 코드나 기대값을 결과에 맞춰 바꾸지 않습니다. **원인을 분석해서 기록**합니다. (조교님 피드백)
- 외부 패키지를 추가하지 않습니다 (표준 라이브러리만 사용). 개인 PC 절대 경로를 쓰지 않습니다.

## 6. 기록 남기기 (주간 보고서용)

- **막힌 점:** 오류가 나면 *입력, 실행 명령, 오류 메시지, 시도한 방법*을 PR이나 팀 채팅방에 남겨 주세요. 해결 못 한 오류도 기록 자체가 보고서 자료입니다.
- **AI 활용:** AI(Claude, ChatGPT 등)를 썼다면 *무엇을 요청했는지, 어떻게 확인했는지, 무엇을 채택·수정했는지* 를 PR 설명에 한두 줄 적어 주세요.
- **원논문과 다르게 구현한 부분:** README의 "원논문과의 차이" 표에 추가해 주세요.

## 7. 13주차 규칙 (반례 탐색·수정)

반례 목록은 [docs/counterexamples.md](docs/counterexamples.md), 추가 사례 형식은 [demo/extra_cases/README.md](demo/extra_cases/README.md)에 있습니다.

1. **기대 결과는 실행 전에 씁니다.** `demo/extra_cases/<담당>.json`에 사례를 추가할 때 `expect`를 "올바른 동작"으로 먼저 적고 `written_before_run: true`로 표시한 뒤 실행합니다. 실행 결과를 보고 기대값을 고치지 않습니다.
2. **고정 사례는 수정하지 않습니다.** `demo/fixed_cases.json`과 `demo/run_demo.py`의 판정은 그대로 두고, 새 사례는 `demo/extra_cases/`에만 추가합니다.
3. **고치기 전에 `evidence/before/`부터 남깁니다.** 지금 코드로 `python3 demo/run_extra.py --case <id>`를 실행해 입력, 명령, 출력, 로그 발췌를 기록하고 커밋한 뒤 수정을 시작합니다.
4. **고친 뒤 같은 입력으로 `evidence/after/`를 남깁니다.** 파일 이름과 형식을 수정 전과 맞추고, `docs/counterexamples.md`의 "처리"와 "수정 전·후" 칸을 갱신합니다.
5. **PR에 AI가 작성한 부분과 직접 확인한 부분을 나눠 적습니다** ([PR 템플릿](.github/pull_request_template.md)). AI가 보고한 실행 결과를 그대로 옮기지 말고, 직접 실행한 명령과 결과를 따로 적습니다.
6. PR 전 체크: `python3 demo/run_demo.py` **15/15**, `python3 demo/run_extra.py` 결과(통과 수와 남은 FAIL 목록)를 PR에 붙입니다.
