#!/usr/bin/env python3
"""p3 연습 데이터 생성. 사용: python3 make_data.py [--out 폴더]"""
import argparse
import csv
import os
import random

TOOLS = [("MT-01", "CD;THK", 22), ("MT-02", "CD;OVL", 25), ("MT-03", "CD;THK;OVL", 18), ("MT-04", "THK", 20)]


def build(seed=5):
    r = random.Random(seed)
    lots = []
    t = 8 * 60 - 90   # 근무 시작 전부터 쌓인 lot 포함
    for i in range(1, 78):
        t += r.choice([3, 5, 6, 8, 10, 12])
        recipe = r.choices(["CD", "THK", "OVL"], weights=[5, 3, 2])[0]
        pri = "HOT" if r.random() < 0.12 else "NORMAL"
        lots.append((f"LOT{i:03d}", f"2026-11-11 {t // 60:02d}:{t % 60:02d}", recipe, pri))
    return lots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    d = os.path.join(a.out, "data")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "lots.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lot_id", "arrival", "recipe", "priority"])
        w.writerows(build())
    with open(os.path.join(d, "tools.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tool_id", "recipes", "minutes_per_lot"])
        w.writerows(TOOLS)
    print(f"lot {len(build())}개, 장비 {len(TOOLS)}대 → {a.out}")


if __name__ == "__main__":
    main()
