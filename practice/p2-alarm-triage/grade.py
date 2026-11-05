#!/usr/bin/env python3
"""p2 채점. 사용: python3 grade.py review_list.csv"""
import argparse
import csv
import os
import sys
from datetime import datetime


def parse(t):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(t.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("review_list")
    ap.add_argument("--answer", default=".answer/incidents.csv")
    ap.add_argument("--data", default="data")
    a = ap.parse_args()
    inc = {(r["equipment_id"], r["alarm_code"]) for r in csv.DictReader(open(a.answer, newline=""))}
    pm = {}
    for r in csv.DictReader(open(os.path.join(a.data, "equipment.csv"), newline="")):
        if r["pm_start"]:
            pm[r["equipment_id"]] = (parse(r["pm_start"]), parse(r["pm_end"]))
    rows = list(csv.DictReader(open(a.review_list, newline="", encoding="utf-8-sig")))
    need = {"rank", "equipment_id", "alarm_code", "first_time", "last_time", "count", "reason"}
    if not rows or not need <= set(rows[0]):
        print(f"FAIL 컬럼 형식: 필요 {sorted(need)}")
        return 1
    rows.sort(key=lambda r: int(float(r["rank"])))
    top = rows[:20]
    pairs = [(r["equipment_id"], r["alarm_code"]) for r in top]
    hit = {p for p in pairs if p in inc}
    dup = len(pairs) - len(set(pairs))
    in_pm = 0
    for r in top:
        if r["equipment_id"] in pm:
            s, e = pm[r["equipment_id"]]
            if s <= parse(r["first_time"]) <= e:
                in_pm += 1
    empty_reason = sum(1 for r in top if not r["reason"].strip())
    print(f"# p2 채점 (상위 20건 기준, 실제 사고 {len(inc)}건)")
    print(f"- 상위 20건에 포함된 실제 사고: {len(hit)}/{len(inc)}")
    missed = sorted({c for e, c in inc} - {c for e, c in hit})
    if missed:
        print(f"- 아예 놓친 사고 코드: {missed}")
    print(f"- 상위 20건 안 같은 (설비, 코드) 중복 줄: {dup}  (같은 사건을 나눠 표시했을 수 있음)")
    print(f"- 상위 20건 안 정비 중 알람: {in_pm}")
    print(f"- 이유가 비어 있는 줄: {empty_reason}")
    ok = len(hit) >= len(inc) * 0.85 and in_pm == 0 and empty_reason == 0
    print(f"- 판정: {'목표 달성' if ok else '개선 필요'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
