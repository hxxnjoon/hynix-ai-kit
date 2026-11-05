#!/usr/bin/env python3
"""지표 교차검증 도구 (표준 라이브러리만 사용).

라이브러리가 낸 수치를 독립적으로 한 번 더 계산해 맞추는 용도다.

사용:
  # 분류: 정답 컬럼과 점수(또는 예측) 컬럼이 있는 CSV
  python3 metrics.py classify pred.csv --y label --score prob --positive 1 --threshold 0.5 --k 0.1
  python3 metrics.py classify pred.csv --y label --pred pred_label --positive 1
  # 회귀
  python3 metrics.py regress pred.csv --y actual --pred predicted
  # 가중 수율: sum(양품)/sum(투입), 그룹별
  python3 metrics.py yield data.csv --good good_cnt --total total_cnt --by tool_id

모듈로 import해서 함수만 써도 된다.
"""
import argparse
import csv
import math
import sys


def confusion(y, p):
    tp = sum(1 for a, b in zip(y, p) if a == 1 and b == 1)
    fp = sum(1 for a, b in zip(y, p) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(y, p) if a == 1 and b == 0)
    tn = sum(1 for a, b in zip(y, p) if a == 0 and b == 0)
    return tp, fp, fn, tn


def safe_div(a, b):
    return a / b if b else None


def classification_report(y, p):
    tp, fp, fn, tn = confusion(y, p)
    prec = safe_div(tp, tp + fp)
    rec = safe_div(tp, tp + fn)
    f1 = safe_div(2 * prec * rec, prec + rec) if prec is not None and rec is not None else None
    spec = safe_div(tn, tn + fp)
    neg_prec = safe_div(tn, tn + fn)
    neg_f1 = safe_div(2 * spec * neg_prec, spec + neg_prec) if spec is not None and neg_prec is not None else None
    macro = (f1 + neg_f1) / 2 if f1 is not None and neg_f1 is not None else None
    bal = (rec + spec) / 2 if rec is not None and spec is not None else None
    return {
        "TP": tp, "FP": fp, "FN": fn, "TN": tn,
        "accuracy": safe_div(tp + tn, len(y)),
        "precision": prec, "recall": rec, "f1": f1,
        "specificity": spec, "balanced_accuracy": bal, "macro_f1": macro,
    }


def roc_auc(y, s):
    """동점은 평균 순위로 처리한 AUC."""
    pairs = sorted(zip(s, y))
    n = len(pairs)
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        for k in range(i, j + 1):
            ranks[k] = (i + j) / 2 + 1
        i = j + 1
    pos = sum(y)
    neg = n - pos
    if not pos or not neg:
        return None
    rs = sum(r for r, (_, t) in zip(ranks, pairs) if t == 1)
    return (rs - pos * (pos + 1) / 2) / (pos * neg)


def average_precision(y, s):
    """sklearn.average_precision_score와 같은 정의(계단식, 동점은 한 번에 처리)."""
    pos = sum(y)
    if not pos:
        return None
    order = sorted(range(len(y)), key=lambda i: -s[i])
    ap = 0.0
    tp = fp = 0
    prev_recall = 0.0
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and s[order[j + 1]] == s[order[i]]:
            j += 1
        for k in range(i, j + 1):
            if y[order[k]] == 1:
                tp += 1
            else:
                fp += 1
        recall = tp / pos
        precision = tp / (tp + fp)
        ap += (recall - prev_recall) * precision
        prev_recall = recall
        i = j + 1
    return ap


def recall_at_k(y, s, k):
    """점수 상위 k(비율 0~1 또는 개수)를 양성으로 선별했을 때 잡히는 양성 비율.
    경계에서 동점이 있으면 정렬 순서에 따라 달라질 수 있으므로 동점 개수도 함께 반환한다."""
    n = len(y)
    cnt = int(round(k * n)) if 0 < k < 1 else int(k)
    cnt = max(0, min(cnt, n))
    pos = sum(y)
    if not pos or cnt == 0:
        return None, cnt, 0
    order = sorted(range(n), key=lambda i: -s[i])
    caught = sum(y[i] for i in order[:cnt])
    ties = 0
    if 0 < cnt < n:
        cut = s[order[cnt - 1]]
        ties = sum(1 for i in order[cnt:] if s[i] == cut)
    return caught / pos, cnt, ties


def regression_report(y, p):
    n = len(y)
    if not n:
        return {}
    err = [a - b for a, b in zip(y, p)]
    mae = sum(abs(e) for e in err) / n
    rmse = math.sqrt(sum(e * e for e in err) / n)
    mean = sum(y) / n
    ss_tot = sum((a - mean) ** 2 for a in y)
    r2 = 1 - sum(e * e for e in err) / ss_tot if ss_tot else None
    return {"n": n, "MAE": mae, "RMSE": rmse, "R2": r2}


def weighted_yield(rows):
    """rows: (group, good, total). 그룹별과 전체 sum(good)/sum(total). 분모 0은 None."""
    agg = {}
    for g, good, total in rows:
        a = agg.setdefault(g, [0.0, 0.0])
        a[0] += good
        a[1] += total
    out = {g: (a[0], a[1], safe_div(a[0], a[1])) for g, a in agg.items()}
    tg = sum(a[0] for a in agg.values())
    tt = sum(a[1] for a in agg.values())
    return out, (tg, tt, safe_div(tg, tt))


def _read(path):
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, newline="", encoding=enc) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"인코딩을 읽지 못했습니다: {path}")


def _fmt(v):
    if v is None:
        return "산출 불가"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def _need(rows, cols, path):
    if not rows:
        raise SystemExit(f"데이터 행이 없습니다: {path}")
    miss = [c for c in cols if c and c not in rows[0]]
    if miss:
        raise SystemExit(f"컬럼이 없습니다: {miss} (있는 컬럼: {list(rows[0])[:20]})")


def cli_classify(a):
    rows = _read(a.file)
    _need(rows, [a.y, a.score, a.pred], a.file)
    pos = str(a.positive)
    rows = [r for r in rows if r[a.y].strip() != ""]
    y = [1 if r[a.y].strip() == pos else 0 for r in rows]
    print(f"# 분류 지표: {a.file} (n={len(y)}, 양성 {sum(y)} = {safe_div(sum(y), len(y)) or 0:.2%})")
    if a.score:
        s = [float(r[a.score]) for r in rows]
        p = [1 if v >= a.threshold else 0 for v in s]
        print(f"- ROC-AUC {_fmt(roc_auc(y, s))} / PR-AUC(AP) {_fmt(average_precision(y, s))} / 양성 비율(무작위 AP) {_fmt(safe_div(sum(y), len(y)))}")
        if a.k:
            r, cnt, ties = recall_at_k(y, s, a.k)
            print(f"- 상위 {cnt}건 선별 시 재현율 {_fmt(r)} (무작위 기대값 {_fmt(cnt / len(y))}){' / 경계 동점 ' + str(ties) + '건 주의' if ties else ''}")
        print(f"- 임계값 {a.threshold} 기준")
    else:
        p = [1 if r[a.pred].strip() == pos else 0 for r in rows]
    rep = classification_report(y, p)
    print("| 지표 | 값 |\n|---|---|")
    for k, v in rep.items():
        print(f"| {k} | {_fmt(v)} |")
    return 0


def cli_regress(a):
    rows = _read(a.file)
    _need(rows, [a.y, a.pred], a.file)
    rows = [r for r in rows if r[a.y].strip() and r[a.pred].strip()]
    y = [float(r[a.y]) for r in rows]
    p = [float(r[a.pred]) for r in rows]
    base = sum(y) / len(y) if y else 0
    print(f"# 회귀 지표: {a.file}")
    print("| 지표 | 모델 | 평균 예측 기준선 |\n|---|---|---|")
    m, b = regression_report(y, p), regression_report(y, [base] * len(y))
    for k in m:
        print(f"| {k} | {_fmt(m[k])} | {_fmt(b.get(k))} |")
    return 0


def cli_yield(a):
    rows = _read(a.file)
    _need(rows, [a.good, a.total, a.by], a.file)
    data = []
    bad = 0
    for r in rows:
        try:
            g, t = float(r[a.good]), float(r[a.total])
        except ValueError:
            bad += 1
            continue
        if g < 0 or t < 0 or g > t:
            bad += 1
        data.append((r[a.by] if a.by else "전체", g, t))
    groups, total = weighted_yield(data)
    print(f"# 가중 수율 sum({a.good}) / sum({a.total})")
    if bad:
        print(f"- 경고: 숫자가 아니거나 음수이거나 양품>투입인 행 {bad}개")
    print("| 그룹 | 양품 | 투입 | 수율 |\n|---|---|---|---|")
    for g, (gd, tt, yv) in sorted(groups.items()):
        print(f"| {g} | {gd:g} | {tt:g} | {_fmt(yv)} |")
    print(f"| **전체** | {total[0]:g} | {total[1]:g} | {_fmt(total[2])} |")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify")
    c.add_argument("file")
    c.add_argument("--y", required=True)
    g = c.add_mutually_exclusive_group(required=True)
    g.add_argument("--score")
    g.add_argument("--pred")
    c.add_argument("--positive", default="1")
    c.add_argument("--threshold", type=float, default=0.5)
    c.add_argument("--k", type=float, help="상위 비율(0~1) 또는 개수")
    r = sub.add_parser("regress")
    r.add_argument("file")
    r.add_argument("--y", required=True)
    r.add_argument("--pred", required=True)
    yd = sub.add_parser("yield")
    yd.add_argument("file")
    yd.add_argument("--good", required=True)
    yd.add_argument("--total", required=True)
    yd.add_argument("--by")
    a = ap.parse_args(argv)
    return {"classify": cli_classify, "regress": cli_regress, "yield": cli_yield}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
