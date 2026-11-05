# hynix-ai-kit

AI 활용 역량 평가(크래프톤 Cofa-Probe 기반, 제공 Codex 사용)를 위한 **개인 준비용 Codex 하네스**.
SK하이닉스 AI 해커톤 2026 본선과 같은 데이터 기반 문제 해결 과제를 기준으로 만들었다.

> 주최사, 크래프톤, OpenAI와 무관한 비공식 자료다. 실제 과제 문제나 정답은 없다.
> **과제 README, 과제 안내, 응시 플랫폼 공식 규칙이 항상 우선한다.**

## 무엇을 하나

Cofa-Probe는 결과물과 함께 **AI와 일한 과정**(대화, 터미널, git 로그, 테스트 결과, 문서)을 수집해
기술, 의도, 인지 세 축으로 평가하고, 제출 후 AI 없이 답하는 서술형으로 이해도를 확인한다.
이 하네스는 정답을 만들지 않는다. 대신 다음을 강제한다.

1. **코드보다 계약 먼저**: 사실, 가정, 담당자 질문, 안 할 일, 완료 조건을 TASK.md에 먼저 적는다
2. **계산은 코드, 해석만 AI**: 숫자는 스크립트 출력으로만 말하고 다른 방법으로 한 번 더 계산한다
3. **핵심 결정은 사람이**: 지표, 분할, 경계값, 결측 정책은 선택지를 보고 사용자가 고르고 기록한다
4. **실행 증거 없이 완료 없음**: PASS / FAIL / NOT_RUN / HUMAN_CHECK 네 상태만 쓴다
5. **설명 가능한 기록**: DECISIONS.md와 FINAL_REVIEW.md가 서술형 답변의 재료가 된다

## 구성

```
AGENTS.md                 Codex 작업 규칙 (설치 시 과제 AGENTS.md 끝에 블록으로 추가)
.agents/skills/
  hk-start/               README 분석, 담당자 인터뷰 질문, 과제 계약
  hk-data/                데이터 계약, 반도체 집계 함정, 모델 누수 점검
    references/semiconductor.md   용어, 데이터 종류, 지표, SPC
  hk-design/              핵심 로직 유형 분류, 선택지 비교, 검증기 먼저
  hk-build/               서비스형 결과물: 최소 스택, 0.0.0.0, 로직 분리, UAT
  hk-verify/              완료 조건 ↔ 테스트, 실패 먼저, 독립 리뷰, preflight
  hk-handoff/             세션 인수인계
  hk-wrap/                동결, 결과 README, 서술형 대비 FINAL_REVIEW
tools/                    표준 라이브러리만 사용 (pandas 없어도 동작)
  profile.py              CSV 요약, 누수 의심 컬럼, 결측과 타깃 관계, 키 중복, 조인 증폭
  metrics.py              분류, 회귀 지표와 가중 수율 교차 계산 (sklearn과 일치 검증)
  preflight.py            환경 점검(--env)과 제출 전 점검. 검사 0건이면 exit 2
templates/                TASK, DECISIONS, HANDOFF, FINAL_REVIEW
practice/                 모의 과제 3종(예측, 서비스, 배정)과 리허설 가이드. 설치되지 않음
install.sh                과제 폴더 설치, 사용자 범위 설치, 설치 확인
tests/                    이 키트 자체 테스트
```

## 설치

과제 폴더 **밖**에 받아서 과제 루트에서 설치한다. 키트 폴더가 제출물에 섞이지 않게 하기 위해서다.

```bash
git clone --depth 1 https://github.com/<계정>/hynix-ai-kit /tmp/hk
bash /tmp/hk/install.sh            # 현재 폴더(과제 루트)에 설치
bash /tmp/hk/install.sh --check    # 설치 확인
```

기존 AGENTS.md는 보존하고 끝에 블록만 추가한다(원본은 `.hk/AGENTS.md.orig`). TASK.md, DECISIONS.md는 없을 때만 만든다.
Codex에게 시켜도 된다: `/tmp/hk/README.md를 읽고 이 과제 폴더에 install.sh로 설치한 뒤 --check까지 실행해줘.`

**과제 폴더에 쓰기 권한이 없을 때**

```bash
bash /tmp/hk/install.sh --user && bash /tmp/hk/install.sh --check --user
```

과제 폴더는 건드리지 않고 `~/.agents/skills/hk-*`, `~/.agents/hynix-ai-kit/`에 설치한다. 설치가 끝나면 출력되는 첫 메시지를 Codex에 보낸다.

**홈에도 쓸 수 없을 때 (설치 없이 쓰기)**: clone만 하고 첫 메시지로 보낸다.

```
/tmp/hk/AGENTS.md를 이 세션 작업 규칙으로 따라줘(과제 안내가 우선). 도구는 /tmp/hk/tools에 있어.
내가 "hk-이름"이라고 하면 /tmp/hk/.agents/skills/hk-이름/SKILL.md를 읽고 그대로 해줘. 먼저 hk-start.
```

설치 후에는 **같은 과제 폴더에서 Codex 새 세션**을 열고 `/skills`로 hk-* 7개가 보이는지 확인한다.

## 당일 흐름

| 시점 | 할 일 | 보내는 메시지 |
|---|---|---|
| 시작 전 | 사전 체험에서 clone, 설치, `codex` 실행, `/model` 확인 | |
| 0분 | 과제 시작, 설치 | `$hk-start 시작 HH:MM, 작업 180분` |
| ~15% | 담당자에게 질문 (사람이 메신저로) → 합의문 승인 | `이 답변을 TASK.md에 반영하고 바뀌는 구현을 알려줘: ...` |
| 데이터 확인 | 데이터 계약, 누수 점검 | `$hk-data` |
| 핵심 로직 | 유형 분류, 선택지 비교 후 선택 | `$hk-design` |
| 화면이 필요하면 | 얇게 끝까지, UAT | `$hk-build` |
| ~35% | 첫 완주: 제출 형식 결과물 생성 | `완료 조건 C1부터 $hk-verify 절차로 진행해` |
| 중간 | 맥락이 길어지면 인수인계 | `$hk-handoff` |
| ~80% | 동결, 독립 리뷰 | `리뷰` → `$hk-wrap` |
| 종료 10분 전 | preflight 후 제출 | |
| 제출 후 | **AI 사용 금지.** FINAL_REVIEW에서 정리한 카드로 직접 답변 | |

언제든 `STATE`(현재 단계, 남은 시간, 미검증 항목) / `근거`(수치의 파일:줄과 명령)를 보낼 수 있다.

## 연습

본선 과제는 공개되지 않았고 2차와 다를 수 있다. `practice/REHEARSAL.md`를 따라 세 유형을 시간 재고 연습한다.
각 과제의 담당자는 숨은 조건을 물어봐야만 알려주고, `grade.py`가 숨겨진 정답으로 채점한다.

## 도구 예시

```bash
python3 .hk/tools/preflight.py --env
python3 .hk/tools/profile.py data/x.csv --target label --key lot_id,wafer_id
python3 .hk/tools/profile.py join data/a.csv data/b.csv --on lot_id,wafer_id
python3 .hk/tools/metrics.py classify result.csv --y label --score prob --k 0.1
python3 .hk/tools/metrics.py yield data/y.csv --good good_cnt --total in_cnt --by tool_id
python3 .hk/tools/preflight.py
```

## 검증한 것

| 주장 | 확인 방법 |
|---|---|
| 도구가 표준 라이브러리만 쓴다 | `tools/*.py` import 확인 |
| 누수 컬럼과 결측-타깃 관계를 잡는다 | 합성 데이터 테스트 (`test_detects_leak_column_and_key_duplicates`) |
| 조인 행 증폭을 잡는다 | `test_join_explosion` |
| ROC-AUC, AP가 sklearn과 같다 | 동점 포함 500행 비교 (`test_matches_sklearn`) |
| 가중 수율과 분모 0 처리 | `test_weighted_yield_is_not_mean_of_ratios`, `test_zero_denominator` |
| 검사 0건, 전부 skip을 통과로 읽지 않는다 | `test_empty_folder_is_not_pass`, `test_all_skipped_tests_fail` |
| pytest가 없어도 `tests/`(`__init__.py` 없음)를 찾아 실행한다 | `test_unittest_runner_without_init_imports_project`, Python 3.9와 3.13에서 전체 테스트 실행 |
| 기존 AGENTS.md 보존, 재설치해도 블록 하나 | `test_project_install_preserves_existing_agents` |
| 쓰기 권한 없으면 --user를 안내 | `test_readonly_folder_points_to_user_mode` |
| 다른 내용의 기존 스킬을 덮어쓰지 않는다 | `test_conflicting_skill_stops` |

```bash
python3 -m unittest discover -s tests -v
```

## 참고한 공개 자료

구조와 원칙을 참고했고 문서와 코드는 새로 작성했다.

- [hamjoon2003/sk-hynix-2nd-harness](https://github.com/hamjoon2003/sk-hynix-2nd-harness): 검사 0건 exit 2, TASK 계약, 서술형 질문 은행 구성
- [JINwonLEE/cofa-codex-harness](https://github.com/JINwonLEE/cofa-codex-harness): 쓰기 권한 없을 때 사용자 범위 설치, 사람 개입 기록, 데이터 계약
- [dogsa33/cofa-kit](https://github.com/dogsa33/cofa-kit): 반도체 수율, 조인, SPC 판단 지침
- [JAM-PARK/codex-harness-kit](https://github.com/JAM-PARK/codex-harness-kit): 산출물에서 입력으로 역대조하는 데이터 공백 점검, 기존 AGENTS 병합 설치
- [zittenyetten/cofa-probe-kit](https://github.com/zittenyetten/cofa-probe-kit): 사전 체험 점검, 서술형 준비 방식
- [크래프톤 FDE 코파톤 후기](https://brunch.co.kr/@luma/5): 평가 3축, 확인 문제 모범 답안 구조, 인수인계의 중요성

## 라이선스

MIT
