# 리허설 가이드

실제 시험처럼 시간을 재고, 담당자를 다른 AI가 연기하게 하고, 끝나면 AI 없이 서술형을 쓴다.
본선 과제는 공개되지 않았고 이 세 과제와 다를 것이다. 목적은 **정답이 아니라 흐름을 몸에 익히는 것**이다.

| 과제 | 유형 | 주로 쓰는 스킬 |
|---|---|---|
| `p1-etch-screening` | 예측 모델, 누수와 지표 | `$hk-data`, `$hk-design` |
| `p2-alarm-triage` | 서비스형 화면 + 우선순위 규칙 | `$hk-build`, `$hk-design` |
| `p3-metrology-dispatch` | 배정과 스케줄링, 필수 제약 | `$hk-design` (검증기 먼저) |

## 준비 (5분)

```bash
mkdir -p ~/rehearsal/p1 && cd ~/rehearsal/p1
python3 <키트>/practice/p1-etch-screening/make_data.py      # data/ 와 .answer/ 생성
cp <키트>/practice/p1-etch-screening/README.md .
git init -q && git add -A && git commit -qm "task"
bash <키트>/install.sh
```

- `.answer/`와 `persona.md`는 **열지 않는다.**
- 다른 AI 대화창에 `persona.md`의 "시스템 지시"를 붙여 넣어 담당자를 만든다. 질문은 그 창에 직접 쓴다.
- Codex가 없으면 연습용으로 다른 코딩 AI를 써도 되지만, 시험 당일에는 제공 Codex만 쓴다.

## 진행 (90분 압축판 또는 180분 실전판)

| 구간 | 할 일 |
|---|---|
| 0~15% | `$hk-start`, 담당자 질문 최소 4개, TASK.md 승인 |
| ~35% | 첫 완주: 제출 파일 생성 |
| ~80% | 완료 조건별 테스트, `리뷰` |
| 마지막 20% | `$hk-wrap`, preflight, FINAL_REVIEW.md 소리 내어 읽기 |

## 채점

```bash
python3 <키트>/practice/p1-etch-screening/grade.py submission.csv
```

## 서술형 (AI 없이, 6문항 × 5분)

FINAL_REVIEW.md를 닫고, `hk-wrap` 질문 은행에서 6개를 골라 메모장에 직접 타이핑한다.
끝나면 기록과 대조해 틀린 숫자, 기록에 없는 주장을 표시한다.

## 3축 셀프 채점

| 축 | 확인 | 예 / 아니오 |
|---|---|---|
| 기술 | 제출 파일이 형식대로 생성되고 README 명령으로 다시 실행된다 | |
| 기술 | 핵심 로직에 테스트가 있고 실패를 먼저 본 적이 있다 | |
| 의도 | 담당자에게 결과를 바꾸는 질문을 했고 답이 구현에 반영됐다 | |
| 의도 | 핵심 결정을 선택지 비교 후 내가 골랐고 DECISIONS.md에 있다 | |
| 의도 | 단계별 커밋이 5개 이상이다 | |
| 인지 | 숫자 카드를 보지 않고 핵심 수치 3개를 말할 수 있다 | |
| 인지 | 결과물이 틀리는 입력을 하나 구체적으로 말할 수 있다 | |
| 인지 | Codex 출력을 믿지 않고 다시 확인한 지점을 말할 수 있다 | |

## 과제별 함정

연습을 마친 뒤 각 `persona.md` 아래의 "함정" 표를 열어 무엇을 놓쳤는지 확인한다.
