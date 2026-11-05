#!/usr/bin/env python3
"""p1 채점. 사용: python3 grade.py submission.csv [--answer .answer/etch_new_labels.csv]"""
import argparse
import csv
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("submission")
    ap.add_argument("--answer", default=".answer/etch_new_labels.csv")
    a = ap.parse_args()
    ans = {(r["lot_id"], r["wafer_id"].zfill(2)): r for r in csv.DictReader(open(a.answer, newline=""))}
    sub = list(csv.DictReader(open(a.submission, newline="", encoding="utf-8-sig")))
    problems = []
    need = {"lot_id", "wafer_id", "score", "screen"}
    if not sub or not need <= set(sub[0]):
        print(f"FAIL 컬럼 형식: 필요 {sorted(need)}, 제출 {list(sub[0]) if sub else '빈 파일'}")
        return 1
    got = {}
    for r in sub:
        k = (r["lot_id"], r["wafer_id"].zfill(2))
        try:
            got[k] = (float(r["score"]), int(float(r["screen"])))
        except ValueError:
            problems.append(f"숫자가 아님: {k}")
    missing = set(ans) - set(got)
    extra = set(got) - set(ans)
    if missing:
        problems.append(f"누락 웨이퍼 {len(missing)}개 (예: {sorted(missing)[:2]})")
    if extra:
        problems.append(f"정답에 없는 웨이퍼 {len(extra)}개")
    n = len(ans)
    fails = [k for k, r in ans.items() if r["fail"] == "1"]
    screened = [k for k, (_, s) in got.items() if s == 1 and k in ans]
    ratio = len(screened) / n
    caught = sum(1 for k in screened if ans[k]["fail"] == "1")
    # 기준선: 현재 경험 규칙 (rf_power 상위 10%)
    base_rank = sorted(ans, key=lambda k: -float(ans[k]["rf_power"]))[: int(n * 0.10)]
    base_caught = sum(1 for k in base_rank if ans[k]["fail"] == "1")
    # 챔버 E만 따로
    e_keys = [k for k in ans if ans[k]["chamber"] == "E"]
    e_fail = [k for k in e_keys if ans[k]["fail"] == "1"]
    e_caught = sum(1 for k in screened if ans[k]["chamber"] == "E" and ans[k]["fail"] == "1")

    print(f"# p1 채점 (웨이퍼 {n}, 불량 {len(fails)} = {len(fails) / n:.1%})")
    for p in problems:
        print(f"- 경고: {p}")
    ok_ratio = ratio <= 0.10 + 1e-9
    print(f"- 선별 비율 {ratio:.1%} {'OK' if ok_ratio else 'FAIL (재검사 용량 10% 초과 → 무효)'}")
    print(f"- 선별로 잡은 불량 {caught}/{len(fails)} = 재현율 {caught / len(fails):.1%}")
    print(f"- 현재 경험 규칙(rf_power 상위 10%) 기준선 재현율 {base_caught / len(fails):.1%}")
    if e_fail:
        print(f"- 신규 챔버 E 불량 {e_caught}/{len(e_fail)} 잡음")
    rec = caught / len(fails) if ok_ratio else 0.0
    verdict = "기준선보다 낮음" if rec <= base_caught / len(fails) else "기준선 대비 개선"
    print(f"- 판정: {verdict}")
    if rec >= 0.95:
        print("- 참고: 너무 높으면 cd_post 같은 계측 후 값을 썼는지 확인하세요 (실제 현장에서는 쓸 수 없음)")
    return 0 if ok_ratio and not missing else 1


if __name__ == "__main__":
    sys.exit(main())
