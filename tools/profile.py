#!/usr/bin/env python3
"""CSV 프로파일러 (표준 라이브러리만 사용).

데이터 파일을 손으로 열거나 통째로 출력하지 않고 요약만 본다.

사용:
  python3 profile.py data.csv
  python3 profile.py data.csv --target label
  python3 profile.py data.csv --key lot_id,wafer_id
  python3 profile.py data.csv --all            # 모든 컬럼 표시 (기본은 의심 컬럼 + 앞 30개)
  python3 profile.py join a.csv b.csv --on lot_id,wafer_id

종료 코드: 0 정상, 1 입력 오류
"""
import argparse
import csv
import math
import re
import sys
from collections import Counter

MISSING = {"", "na", "n/a", "nan", "null", "none", "-", "?"}
LEAK_PATTERN = re.compile(
    r"(post|after|final|result|judge|judg|verdict|outcome|label|target|flag|"
    r"defect_?c(ou)?nt|fail|pass|yield|measure|meas|metro|inspect|reject|scrap|rework)",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}([ T]\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?)?(Z|[+-]\d{2}:?\d{2})?$")
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def is_missing(v):
    return v is None or v.strip().lower() in MISSING


def to_float(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def read_csv(path, max_rows=None):
    """utf-8-sig, cp949 순서로 시도한다. (header, rows, encoding, delimiter)"""
    last_err = None
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, newline="", encoding=enc) as f:
                sample = f.read(65536)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
                    delim = dialect.delimiter
                except csv.Error:
                    delim = ","
                reader = csv.reader(f, delimiter=delim)
                header = next(reader, None)
                if header is None:
                    return [], [], enc, delim
                header = [h.strip() for h in header]
                rows = []
                for i, row in enumerate(reader):
                    if max_rows is not None and i >= max_rows:
                        break
                    if len(row) < len(header):
                        row = row + [""] * (len(header) - len(row))
                    rows.append(row[: len(header)])
                return header, rows, enc, delim
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise SystemExit(f"인코딩을 읽지 못했습니다: {path} ({last_err})")


def infer_type(values):
    present = [v.strip() for v in values if not is_missing(v)]
    if not present:
        return "empty"
    n = len(present)
    ints = sum(1 for v in present if re.fullmatch(r"[+-]?\d+", v))
    nums = sum(1 for v in present if to_float(v) is not None)
    dates = sum(1 for v in present[:2000] if DATE_PATTERN.match(v))
    if ints == n:
        if any(len(v) > 1 and v.startswith("0") for v in present):
            return "id(앞자리0)"
        return "int"
    if nums == n:
        return "float"
    if dates >= 0.95 * min(n, 2000):
        return "datetime"
    if nums >= 0.9 * n:
        return "숫자혼합"
    return "str"


def auc_binary(xs, ys):
    """Mann-Whitney 기반 AUC. ys는 0/1. 동점은 평균 순위."""
    pairs = sorted(zip(xs, ys))
    n = len(pairs)
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = r
        i = j + 1
    pos = sum(1 for _, y in pairs if y == 1)
    neg = n - pos
    if pos == 0 or neg == 0:
        return None
    rank_sum = sum(r for r, (_, y) in zip(ranks, pairs) if y == 1)
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def binarize_target(values):
    """타깃을 0/1로. 두 클래스가 아니면 None. 소수 클래스를 1로 둔다."""
    present = [v.strip() for v in values if not is_missing(v)]
    cnt = Counter(present)
    if len(cnt) != 2:
        return None, None
    (a, ca), (b, cb) = cnt.most_common()
    positive = b  # 소수 클래스
    return positive, [None if is_missing(v) else int(v.strip() == positive) for v in values]


def category_purity(xs, ys):
    """범주별 다수 클래스 정확도(가중). 범주가 타깃을 거의 결정하면 1에 가깝다."""
    groups = {}
    for x, y in zip(xs, ys):
        groups.setdefault(x, Counter())[y] += 1
    correct = sum(c.most_common(1)[0][1] for c in groups.values())
    return correct / len(xs), len(groups)


def profile(args):
    header, rows, enc, delim = read_csv(args.file, args.max_rows)
    n = len(rows)
    out = []
    p = out.append
    p(f"# 프로파일: {args.file}")
    p(f"- 행 {n:,} (헤더 제외{', 상한 ' + format(args.max_rows, ',') + '행까지 읽음' if args.max_rows and n >= args.max_rows else ''}), 열 {len(header)}, 인코딩 {enc}, 구분자 {delim!r}")
    if n == 0:
        p("- 데이터 행이 없습니다.")
        print("\n".join(out))
        return 0

    dup_header = [h for h, c in Counter(header).items() if c > 1]
    if dup_header:
        p(f"- 경고: 중복 컬럼명 {dup_header}")
    full_dup = n - len(set(map(tuple, rows)))
    p(f"- 완전 중복 행: {full_dup:,}")

    cols = list(zip(*rows))
    target_idx = header.index(args.target) if args.target else None
    if args.target and target_idx is None:
        raise SystemExit(f"타깃 컬럼이 없습니다: {args.target}")

    ybin = positive = None
    if target_idx is not None:
        tvals = cols[target_idx]
        cnt = Counter(v.strip() for v in tvals if not is_missing(v))
        miss = sum(1 for v in tvals if is_missing(v))
        p(f"\n## 타깃 `{args.target}`")
        for k, c in cnt.most_common(10):
            p(f"- {k!r}: {c:,} ({c / n:.2%})")
        if miss:
            p(f"- 결측: {miss:,}")
        positive, ybin = binarize_target(tvals)
        if positive is not None:
            p(f"- 이진 타깃으로 보고 소수 클래스 {positive!r}를 양성(1)으로 둡니다. 다수 클래스만 맞혀도 정확도 {1 - sum(y for y in ybin if y is not None) / sum(1 for y in ybin if y is not None):.2%}")

    p("\n## 컬럼")
    p("| 컬럼 | 타입 | 결측% | 고유값 | 요약 | 의심 |")
    p("|---|---|---|---|---|---|")
    flagged_lines, normal_lines = [], []
    leak_candidates = []
    for i, name in enumerate(header):
        vals = cols[i]
        miss = sum(1 for v in vals if is_missing(v))
        present = [v.strip() for v in vals if not is_missing(v)]
        uniq = len(set(present))
        t = infer_type(vals)
        flags = []
        summary = ""
        if t in ("int", "float"):
            nums = [to_float(v) for v in present]
            nums = [x for x in nums if x is not None]
            if nums:
                mean = sum(nums) / len(nums)
                summary = f"min {min(nums):g} / mean {mean:.4g} / max {max(nums):g}"
                if min(nums) < 0 and re.search(r"(cnt|count|qty|num|수량|개수)", name, re.I):
                    flags.append("음수 수량")
        else:
            top = Counter(present).most_common(3)
            summary = ", ".join(f"{k[:20]}({c})" for k, c in top)
        if uniq <= 1:
            flags.append("상수")
        if t == "id(앞자리0)":
            flags.append("문자열로 읽기")
        if t == "숫자혼합":
            flags.append("숫자 아닌 값 섞임")
        if n and miss / n >= 0.3:
            flags.append("결측 많음")
        if uniq == len(present) and len(present) == n and t not in ("float",):
            flags.append("고유(키 후보)")
        if i != target_idx and LEAK_PATTERN.search(name):
            flags.append("이름상 사후값?")
            leak_candidates.append(name)

        if ybin is not None and i != target_idx and uniq > 1:
            idx = [k for k in range(n) if ybin[k] is not None and not is_missing(vals[k])]
            if len(idx) >= 20:
                ys = [ybin[k] for k in idx]
                if t in ("int", "float"):
                    xs = [to_float(vals[k]) for k in idx]
                    auc = auc_binary(xs, ys)
                    if auc is not None:
                        strength = abs(auc - 0.5) * 2
                        if strength >= 0.9:
                            flags.append(f"단일컬럼 AUC {auc:.3f} 누수?")
                            leak_candidates.append(name)
                elif uniq <= max(50, len(idx) // 20):
                    xs = [vals[k].strip() for k in idx]
                    purity, g = category_purity(xs, ys)
                    base = max(sum(ys), len(ys) - sum(ys)) / len(ys)
                    if purity >= 0.99 and purity - base >= 0.02:
                        flags.append(f"범주가 타깃 결정 {purity:.3f} 누수?")
                        leak_candidates.append(name)
            # 결측 여부 자체가 타깃과 관련 있는지
            if miss and miss < n:
                miss_y = [ybin[k] for k in range(n) if is_missing(vals[k]) and ybin[k] is not None]
                pres_y = [ybin[k] for k in range(n) if not is_missing(vals[k]) and ybin[k] is not None]
                if len(miss_y) >= 10 and pres_y:
                    r1, r0 = sum(miss_y) / len(miss_y), sum(pres_y) / len(pres_y)
                    if r0 > 0 and (r1 / r0 >= 2 or r1 / r0 <= 0.5):
                        flags.append(f"결측행 양성률 {r1:.1%} vs {r0:.1%}")

        line = f"| {name} | {t} | {miss / n:.1%} | {uniq:,} | {summary} | {', '.join(flags)} |"
        (flagged_lines if flags else normal_lines).append(line)

    shown = flagged_lines + normal_lines
    if not args.all and len(shown) > 30 + len(flagged_lines):
        hidden = len(shown) - (30 + len(flagged_lines))
        shown = flagged_lines + normal_lines[:30]
        out.extend(shown)
        p(f"\n(의심 없는 컬럼 {hidden}개 생략, `--all`로 전체 표시)")
    else:
        out.extend(shown)

    if args.key:
        keys = [k.strip() for k in args.key.split(",")]
        missing_keys = [k for k in keys if k not in header]
        if missing_keys:
            raise SystemExit(f"키 컬럼이 없습니다: {missing_keys}")
        ki = [header.index(k) for k in keys]
        kc = Counter(tuple(r[i].strip() for i in ki) for r in rows)
        dups = {k: c for k, c in kc.items() if c > 1}
        p(f"\n## 키 {keys}")
        p(f"- 고유 키 {len(kc):,} / 행 {n:,} → 중복 키 {len(dups):,}개 ({sum(dups.values()) - len(dups):,}행 초과)")
        if dups:
            conflict = 0
            groups = {}
            for r in rows:
                groups.setdefault(tuple(r[i].strip() for i in ki), set()).add(tuple(r))
            conflict = sum(1 for k in dups if len(groups[k]) > 1)
            p(f"- 같은 키인데 다른 값을 가진 키: {conflict:,}개 (재검사 이력인지 오류인지 확인 필요)")
            for k, c in list(dups.items())[:3]:
                p(f"  - 예: {k} × {c}")

    p("\n## 확인할 것")
    if leak_candidates:
        p(f"- 누수 후보: {', '.join(dict.fromkeys(leak_candidates))} → 예측 시점에 알 수 있는 값인지 담당자나 데이터 사전으로 확인")
    if full_dup:
        p("- 완전 중복 행이 실제 중복 기록인지 오류인지 확인")
    p("- 한 행의 의미, 식별 키, 시간 기준을 TASK.md 데이터 계약에 문장으로 적기")
    print("\n".join(out))
    return 0


def join_check(args):
    keys = [k.strip() for k in args.on.split(",")]
    ha, ra, _, _ = read_csv(args.left)
    hb, rb, _, _ = read_csv(args.right)
    for h, path in ((ha, args.left), (hb, args.right)):
        miss = [k for k in keys if k not in h]
        if miss:
            raise SystemExit(f"{path}에 키 컬럼이 없습니다: {miss}")
    ia = [ha.index(k) for k in keys]
    ib = [hb.index(k) for k in keys]
    ca = Counter(tuple(r[i].strip() for i in ia) for r in ra)
    cb = Counter(tuple(r[i].strip() for i in ib) for r in rb)
    inner = sum(ca[k] * cb[k] for k in ca if k in cb)
    left_join = sum(ca[k] * cb.get(k, 1) for k in ca)
    only_a = sum(c for k, c in ca.items() if k not in cb)
    only_b = sum(c for k, c in cb.items() if k not in ca)
    print(f"# 조인 점검: {args.left} ⋈ {args.right} on {keys}")
    print(f"- 왼쪽 {len(ra):,}행 / 고유 키 {len(ca):,} ({'유일' if len(ca) == len(ra) else '중복 있음'})")
    print(f"- 오른쪽 {len(rb):,}행 / 고유 키 {len(cb):,} ({'유일' if len(cb) == len(rb) else '중복 있음'})")
    print(f"- inner join 결과 {inner:,}행, left join 결과 {left_join:,}행")
    print(f"- 왼쪽에만 있는 행 {only_a:,}, 오른쪽에만 있는 행 {only_b:,}")
    if left_join > len(ra):
        print(f"- 경고: left join 후 행이 {left_join / len(ra):.2f}배로 늘어납니다. 오른쪽을 먼저 집계하거나 키를 추가하세요.")
    else:
        print("- 행 증폭 없음")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "join":
        ap = argparse.ArgumentParser(prog="profile.py join")
        ap.add_argument("left")
        ap.add_argument("right")
        ap.add_argument("--on", required=True)
        return join_check(ap.parse_args(argv[1:]))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--target")
    ap.add_argument("--key")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--max-rows", type=int, default=1_000_000)
    return profile(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
