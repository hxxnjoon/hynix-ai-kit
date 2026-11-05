#!/usr/bin/env python3
"""p3 채점과 기준선. 풀이 코드와 독립된 검증기다.

사용:
  python3 grade.py schedule.csv          # 제출 채점
  python3 grade.py --baseline out.csv    # 현재 방식(도착 순, 비는 장비, 정비 무시) 일정 생성
"""
import argparse
import csv
import os
import sys
from datetime import datetime, timedelta

QTIME = timedelta(hours=4)
SHIFT = (datetime(2026, 11, 11, 8, 0), datetime(2026, 11, 11, 20, 0))
PM = {"MT-03": (datetime(2026, 11, 11, 10, 0), datetime(2026, 11, 11, 12, 0))}


def t(s):
    return datetime.strptime(s.strip()[:16], "%Y-%m-%d %H:%M")


def load(data):
    lots = {r["lot_id"]: r for r in csv.DictReader(open(os.path.join(data, "lots.csv"), newline=""))}
    tools = {r["tool_id"]: (set(r["recipes"].split(";")), int(r["minutes_per_lot"]))
             for r in csv.DictReader(open(os.path.join(data, "tools.csv"), newline=""))}
    return lots, tools


def evaluate(sched, lots, tools):
    v = []
    seen = {}
    by_tool = {}
    for r in sched:
        lid, tid = r["lot_id"], r["tool_id"]
        if lid not in lots:
            v.append(f"알 수 없는 lot {lid}")
            continue
        if lid in seen:
            v.append(f"중복 배정 {lid}")
        seen[lid] = r
        if tid not in tools:
            v.append(f"알 수 없는 장비 {tid}")
            continue
        s, e = t(r["start"]), t(r["end"])
        lot = lots[lid]
        if lot["recipe"] not in tools[tid][0]:
            v.append(f"레시피 불가 {lid}({lot['recipe']}) → {tid}")
        if s < t(lot["arrival"]):
            v.append(f"도착 전 시작 {lid}")
        if (e - s) < timedelta(minutes=tools[tid][1]):
            v.append(f"소요 시간 부족 {lid}")
        if s < SHIFT[0] or e > SHIFT[1]:
            v.append(f"근무 시간 밖 {lid} {r['start']}~{r['end']}")
        if tid in PM and s < PM[tid][1] and e > PM[tid][0]:
            v.append(f"정비 시간 배정 {lid} → {tid}")
        if s - t(lot["arrival"]) > QTIME:
            v.append(f"Q-time 초과 {lid} 대기 {int((s - t(lot['arrival'])).total_seconds() // 60)}분")
        by_tool.setdefault(tid, []).append((s, e, lid))
    for tid, xs in by_tool.items():
        xs.sort()
        for (s1, e1, a), (s2, e2, b) in zip(xs, xs[1:]):
            if s2 < e1:
                v.append(f"겹침 {tid}: {a}와 {b}")
    unscheduled = sorted(set(lots) - set(seen))
    wait = {lid: (t(r["start"]) - t(lots[lid]["arrival"])).total_seconds() / 60 for lid, r in seen.items()}
    hot = sum(w for l, w in wait.items() if lots[l]["priority"] == "HOT")
    qv = sum(1 for x in v if x.startswith("Q-time"))
    return v, unscheduled, qv, hot, sum(wait.values())


def baseline(lots, tools):
    free = {k: SHIFT[0] for k in tools}
    out = []
    for lid, lot in sorted(lots.items(), key=lambda x: x[1]["arrival"]):
        best = None
        for tid, (rec, m) in tools.items():
            if lot["recipe"] not in rec:
                continue
            s = max(free[tid], t(lot["arrival"]), SHIFT[0])
            if best is None or s < best[1]:
                best = (tid, s, m)
        tid, s, m = best
        e = s + timedelta(minutes=m)
        free[tid] = e
        out.append({"lot_id": lid, "tool_id": tid, "start": s.strftime("%Y-%m-%d %H:%M"), "end": e.strftime("%Y-%m-%d %H:%M")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("schedule", nargs="?")
    ap.add_argument("--data", default="data")
    ap.add_argument("--baseline")
    a = ap.parse_args()
    lots, tools = load(a.data)
    base = baseline(lots, tools)
    if a.baseline:
        with open(a.baseline, "w", newline="") as f:
            w = csv.DictWriter(f, ["lot_id", "tool_id", "start", "end"])
            w.writeheader()
            w.writerows(base)
        print(f"기준선 일정 저장: {a.baseline}")
        return 0
    if not a.schedule:
        ap.error("schedule.csv 경로가 필요합니다")
    sched = list(csv.DictReader(open(a.schedule, newline="", encoding="utf-8-sig")))
    v, uns, qv, hot, total = evaluate(sched, lots, tools)
    bv, buns, bqv, bhot, btotal = evaluate(base, lots, tools)
    hard = [x for x in v if not x.startswith("Q-time")]
    print(f"# p3 채점 (lot {len(lots)})")
    print(f"- 필수 제약 위반(레시피, 겹침, 시간, 정비): {len(hard)}건")
    for x in hard[:10]:
        print(f"  - {x}")
    print(f"- Q-time 위반: {qv}건 (현재 방식 {bqv}건)")
    print(f"- 미배정 lot: {len(uns)}개" + (f" {uns[:5]}" if uns else ""))
    print(f"- HOT 대기 합: {hot:.0f}분 (현재 방식 {bhot:.0f}분)")
    print(f"- 전체 대기 합: {total:.0f}분 (현재 방식 {btotal:.0f}분)")
    print(f"- 참고: 현재 방식은 정비 시간 위반 {sum(1 for x in bv if x.startswith('정비'))}건을 포함")
    ok = not hard and qv == 0 and not uns
    print(f"- 판정: {'유효한 일정' if ok else '무효 또는 위반 있음'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
