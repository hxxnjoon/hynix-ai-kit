#!/usr/bin/env python3
"""p1 연습 데이터 생성. 같은 시드면 항상 같은 데이터. 숨은 정답은 .answer/ 아래에 둔다.

사용: python3 make_data.py [--out 폴더]
"""
import argparse
import csv
import math
import os
import random

CHAMBERS_OLD = ["A", "B", "C", "D"]


def wafer(r, lot, w, day, chamber, lot_drift, comm_bad):
    # 숨은 불량 요인: rf_power 편차, 압력 이상, 챔버 C의 약한 상태, 통신 불량 날
    rf_base = {"A": 500, "B": 502, "C": 498, "D": 501, "E": 520}[chamber]
    rf = r.gauss(rf_base + lot_drift, 6)
    pressure = r.gauss(30 + (0.8 if chamber == "C" else 0), 1.2)
    gas = r.gauss(120, 4)
    temp = r.gauss(60, 0.8)
    z = 0.22 * max(0.0, rf - rf_base) + 1.4 * max(0.0, abs(pressure - 30) - 1.5) + (0.8 if chamber == "C" else 0) + (1.8 if comm_bad else 0) - 5.4
    p = 1 / (1 + math.exp(-z))
    fail = 1 if r.random() < p else 0
    temp_missing = comm_bad and r.random() < 0.7
    cd_post = r.gauss(45 + (6 if fail else 0), 0.8)
    ts = f"2026-{9 + day // 30:02d}-{day % 30 + 1:02d} {r.randint(0, 23):02d}:{r.randint(0, 59):02d}:00"
    return {
        "lot_id": lot, "wafer_id": f"{w:02d}", "ts": ts, "chamber": chamber,
        "rf_power": f"{rf:.1f}", "pressure": f"{pressure:.2f}", "gas_flow": f"{gas:.1f}",
        "temp": "" if temp_missing else f"{temp:.2f}", "cd_post": f"{cd_post:.2f}", "fail": fail,
    }


def build(seed=7):
    r = random.Random(seed)
    train, new = [], []
    for li in range(320):
        day = li // 6
        is_new = day >= 36
        chamber = r.choice(CHAMBERS_OLD + (["E"] if is_new else []))
        lot = f"LT{li:04d}"
        drift = r.gauss(0, 5)
        comm_bad = r.random() < 0.08
        for w in range(1, 26):
            row = wafer(r, lot, w, day, chamber, drift, comm_bad)
            (new if is_new else train).append(row)
    return train, new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    train, new = build()
    os.makedirs(os.path.join(a.out, "data"), exist_ok=True)
    os.makedirs(os.path.join(a.out, ".answer"), exist_ok=True)
    cols = ["lot_id", "wafer_id", "ts", "chamber", "rf_power", "pressure", "gas_flow", "temp", "cd_post", "fail"]
    with open(os.path.join(a.out, "data", "etch_train.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(train)
    with open(os.path.join(a.out, "data", "etch_new.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, cols[:-1], extrasaction="ignore")
        w.writeheader()
        w.writerows(new)
    with open(os.path.join(a.out, ".answer", "etch_new_labels.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["lot_id", "wafer_id", "chamber", "rf_power", "fail"], extrasaction="ignore")
        w.writeheader()
        w.writerows(new)
    print(f"train {len(train)}행 (불량 {sum(x['fail'] for x in train)}), new {len(new)}행 → {a.out}")


if __name__ == "__main__":
    main()
