# 수정 후 증거

반례를 고친 뒤, **`evidence/before/`와 같은 입력·같은 명령**으로 다시 실행한 결과를 여기에 넣는다.

- 파일 이름은 수정 전 파일과 같게 한다 (예: `evidence/before/a_negative_length.md` → `evidence/after/a_negative_length.md`).
- 형식도 같게 한다: 기준 커밋, 실행 환경, 입력, 실행 명령, 출력표, 관찰, 로그 발췌.
- 수정 전과 비교해 바뀐 점과 바뀌지 않은 점을 "관찰"에 적는다.
- `python3 demo/run_extra.py --case <사례 id>` 결과와 `python3 demo/run_demo.py` 결과(15/15)를 함께 붙인다.
- 기대 결과(`demo/extra_cases/`, `demo/fixed_cases.json`)와 판정 코드는 결과에 맞춰 바꾸지 않는다.
- 다 넣었으면 `docs/counterexamples.md`의 "처리"와 "수정 전·후" 칸을 갱신한다.
