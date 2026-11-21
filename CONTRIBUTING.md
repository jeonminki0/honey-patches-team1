# 팀 작업 규칙 (1팀 · Honey-Patch 구현)

> 작업을 시작하기 전에 이 문서를 꼭 읽어 주세요.
> 프로젝트 설명과 실행 방법은 [README.md](README.md)에 있습니다.

## 1. 처음 한 번만: 저장소 받기와 실행 확인

```bash
git clone <저장소 주소>
cd <저장소 이름>
python demo/run_demo.py        # Windows는 py, macOS/Linux는 python3 일 수 있음
```

- 마지막 줄에 **`15/15 통과`** 가 나오면 정상입니다.
- 결과는 [README.md](README.md) 맨 아래 **"재현 기록"** 표에 한 줄 추가해 주세요 (이름, OS, Python 버전, 결과).
- 오류가 나면 코드를 고치지 말고, 오류 메시지를 그대로 팀 채팅방에 공유해 주세요.

## 2. 브랜치: 각자 자기 브랜치를 만들어 작업

main에서 바로 작업하지 않습니다. 아래 이름 규칙으로 **각자 브랜치를 만들어** 작업해 주세요.

| 담당 | 담당 파일 | 브랜치 이름 |
|---|---|---|
| 팀원1 서버 | `server/app.py` | `feat/server` |
| 팀원2 프록시 | `proxy/proxy.py` | `feat/proxy` |
| 팀원3 hp·redaction | `honeypatch/` | `feat/honeypatch` |
| 팀원4 데모·측정 | `demo/` | `feat/demo` |
| 팀원5 문서 | `README.md`, 보고서 | `docs/readme` |

```bash
git switch main
git pull                          # 최신 main 받기
git switch -c feat/proxy          # 내 브랜치 만들기 (이름은 위 표 참고)
git push -u origin feat/proxy     # 처음 한 번만
```

- 담당 파일 외의 파일을 고쳐야 하면, 먼저 해당 담당자에게 말해 주세요. 같은 파일을 동시에 고치면 충돌이 납니다.

## 3. 작업 흐름

```bash
git switch feat/proxy             # 내 브랜치에서
# ... 작업 ...
python demo/run_demo.py           # 실행해서 결과 확인
git add .
git commit -m "feat: 미끼 release 추가"
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
  - [ ] PR 설명에 **무엇을 바꿨는지 + 실행 결과(통과 수)** 붙이기
- **다른 팀원 1명**이 확인하고 merge합니다. 본인 PR을 본인이 merge하지 않습니다.

## 5. 절대 하지 않을 것

- `demo/fixed_cases.json` 의 고정 검증 사례 3종을 수정하지 않습니다. (11주차 고정 규칙, 14주차까지 그대로 제출)
- 결과가 기대와 다르다고 판정 코드나 기대값을 결과에 맞춰 바꾸지 않습니다. **원인을 분석해서 기록**합니다. (조교님 피드백)
- 외부 패키지를 추가하지 않습니다 (표준 라이브러리만 사용). 개인 PC 절대 경로를 쓰지 않습니다.

## 6. 기록 남기기 (주간 보고서용)

- **막힌 점:** 오류가 나면 *입력, 실행 명령, 오류 메시지, 시도한 방법*을 PR이나 팀 채팅방에 남겨 주세요. 해결 못 한 오류도 기록 자체가 보고서 자료입니다.
- **AI 활용:** AI(Claude, ChatGPT 등)를 썼다면 *무엇을 요청했는지, 어떻게 확인했는지, 무엇을 채택·수정했는지* 를 PR 설명에 한두 줄 적어 주세요.
- **원논문과 다르게 구현한 부분:** README의 "원논문과의 차이" 표에 추가해 주세요.
