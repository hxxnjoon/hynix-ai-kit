#!/usr/bin/env python3
"""p2 연습 데이터 생성. 사용: python3 make_data.py [--out 폴더]"""
import argparse
import csv
import os
import random
from datetime import datetime, timedelta

CODES = [
    ("E-101", 1, "챔버 온도 경고 범위 근접"), ("E-102", 1, "가스 유량 미세 변동"), ("E-205", 2, "웨이퍼 정렬 재시도"),
    ("E-230", 2, "로봇 암 속도 저하"), ("E-310", 3, "챔버 압력 상한 초과"), ("E-333", 3, "히터 단선 의심"),
    ("E-417", 2, "진공 누설 감지 - 진공도 회복 지연"), ("E-502", 2, "RF 반사파 증가 - 플라즈마 불안정"),
    ("E-120", 1, "도어 센서 순간 신호"), ("E-240", 2, "냉각수 온도 편차"),
]
REAL_SEV = {"E-417": 3, "E-502": 3}
START = datetime(2026, 10, 19, 0, 0)


def build(seed=11):
    r = random.Random(seed)
    eqs = [f"ETCH-{i:02d}" for i in range(1, 13)]
    pm = {"ETCH-04": (START + timedelta(days=9, hours=8), START + timedelta(days=9, hours=20)),
          "ETCH-09": (START + timedelta(days=12, hours=1), START + timedelta(days=12, hours=9))}
    alarms, incidents = [], []

    def burst(eq, code, t, n, gap_min):
        for i in range(n):
            alarms.append((eq, code, t + timedelta(minutes=i * gap_min + r.random())))

    for _ in range(1400):   # 잡음 알람
        code = r.choice(CODES[:4] + CODES[8:])[0]
        burst(r.choice(eqs), code, START + timedelta(minutes=r.randint(0, 14 * 24 * 60)), r.choice([1, 1, 1, 2, 3]), r.choice([2, 4, 7]))
    # 시끄럽지만 덜 중요한 반복 (등급 2, 많이 반복)
    for _ in range(25):
        burst(r.choice(eqs), "E-230", START + timedelta(minutes=r.randint(0, 14 * 24 * 60)), r.randint(8, 15), 3)
    # 정비 중 등급 3 알람 (봐야 하지 않음)
    for eq, (s, e) in pm.items():
        for _ in range(6):
            burst(eq, r.choice(["E-310", "E-333"]), s + timedelta(minutes=r.randint(10, int((e - s).total_seconds() // 60) - 40)), r.randint(2, 5), 3)
    # 실제 사고: 등급 3 코드 + 오등록 코드
    for k in range(14):
        eq = r.choice([e for e in eqs if e not in pm])
        code = ["E-417", "E-502", "E-310", "E-333"][k % 4]
        t = START + timedelta(days=13, hours=r.randint(0, 23), minutes=r.randint(0, 59)) if k < 8 else START + timedelta(minutes=r.randint(0, 13 * 24 * 60))
        burst(eq, code, t, r.randint(1, 4), r.choice([2, 5]))
        incidents.append((eq, code))
    alarms.sort(key=lambda x: x[2])
    return eqs, pm, alarms, incidents


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    eqs, pm, alarms, incidents = build()
    d = os.path.join(a.out, "data")
    os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(a.out, ".answer"), exist_ok=True)
    with open(os.path.join(d, "alarm_codes.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["alarm_code", "severity", "description"])
        w.writerows(CODES)
    with open(os.path.join(d, "equipment.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["equipment_id", "area", "pm_start", "pm_end"])
        for e in eqs:
            s, t = pm.get(e, (None, None))
            w.writerow([e, "ETCH", s.strftime("%Y-%m-%d %H:%M") if s else "", t.strftime("%Y-%m-%d %H:%M") if t else ""])
    with open(os.path.join(d, "alarms.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["alarm_id", "equipment_id", "alarm_code", "occurred_at"])
        for i, (e, c, t) in enumerate(alarms, 1):
            w.writerow([f"A{i:06d}", e, c, t.strftime("%Y-%m-%d %H:%M:%S")])
    with open(os.path.join(a.out, ".answer", "incidents.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["equipment_id", "alarm_code"])
        w.writerows(sorted(set(incidents)))
    print(f"알람 {len(alarms)}건, 실제 사고 {len(set(incidents))}건 → {a.out}")


if __name__ == "__main__":
    main()
