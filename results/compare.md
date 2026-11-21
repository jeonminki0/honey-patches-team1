# 보호 적용 전·후(모드별) 결과 비교

| 사례 | 모드 | status | 길이 | 비밀 노출 | fork | 응답(앞 40자) |
|---|---|---|---|---|---|---|
| normal | unpatched | 200 | 5 | 0 | 0 | `'hello'` |
| normal | patched | 200 | 5 | 0 | 0 | `'hello'` |
| normal | honeypatched | 200 | 5 | 0 | 0 | `'hello'` |
| violation | unpatched | 200 | 64 | 5 | 0 | `'hi9f2c4e81a7b3d065|alice|10.0.0.23;51d8e'` |
| violation | patched | 400 | 13 | 0 | 0 | `'bad heartbeat'` |
| violation | honeypatched | 200 | 64 | 0 | 1 | `'hi7141270de8880f57|ffye8|73.3.9.96;34711'` |
| boundary | unpatched | 200 | 6 | 0 | 0 | `'hello9'` |
| boundary | patched | 400 | 13 | 0 | 0 | `'bad heartbeat'` |
| boundary | honeypatched | 200 | 6 | 0 | 1 | `'hello2'` |

## 기대 결과 대조

- [PASS] normal: 세 모드 모두 200·'hello'
- [PASS] normal: 세 모드 fork 0회
- [PASS] normal: 허니패치: 타깃으로만 전달
- [PASS] violation: 미패치: 200·64B·비밀 포함
- [PASS] violation: 패치: 400 거부
- [PASS] violation: 허니패치: fork 1회
- [PASS] violation: 허니패치: 200·64B
- [PASS] violation: 허니패치: 실제 비밀 0건
- [PASS] violation: 허니패치: 후속 요청 미끼로
- [PASS] violation: 허니패치: 동시 정상 사용자 타깃·200 hello
- [PASS] boundary: 패치: 400 거부
- [PASS] boundary: 허니패치: fork 1회
- [PASS] boundary: 허니패치: 200·6B
- [PASS] boundary: 허니패치: 6번째 바이트가 진짜 값과 다름
- [PASS] boundary: 허니패치: 실제 비밀 0건

**15/15 통과**