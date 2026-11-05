#!/usr/bin/env python3
"""환경과 제출 상태 점검 (표준 라이브러리만 사용).

사용:
  python3 preflight.py --env          # 시작 시: 이 기계에서 무엇을 쓸 수 있나
  python3 preflight.py                # 제출 전: 기록, 테스트, git, 비밀값 점검
  python3 preflight.py --root DIR     # 과제 루트 지정 (기본: 현재 폴더)
  python3 preflight.py --no-tests     # 테스트 실행 생략
  python3 preflight.py --runner unittest   # pytest 대신 unittest로 실행

종료 코드:
  0  검사한 항목이 모두 정상 (정답 증명은 아님)
  1  문제가 있는 항목이 있음
  2  검사한 항목이 0건이거나 통과 항목이 없음. 통과로 읽지 말 것
"""
import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

SKIP_DIRS = {".git", ".hk", ".agents", "node_modules", ".venv", "venv", "__pycache__", ".ipynb_checkpoints", ".pytest_cache"}
PACKAGES = ["numpy", "pandas", "sklearn", "scipy", "lightgbm", "xgboost", "matplotlib",
            "seaborn", "statsmodels", "pytest", "fastapi", "uvicorn", "flask", "streamlit", "torch"]
PLACEHOLDER = re.compile(r"(TODO|FIXME|TBD|___|Status: `TEMPLATE`|여기에 작성)")
SECRET = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|"
    r"(?i:(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]))"
)
KIT_DOCS = {"TASK.md", "DECISIONS.md", "HANDOFF.md", "FINAL_REVIEW.md"}
TEXT_EXT = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".sh", ".js", ".ts", ".ipynb", ".csv"}


class Report:
    def __init__(self):
        self.rows = []

    def add(self, status, item, detail=""):
        self.rows.append((status, item, detail))

    def print(self):
        for s, i, d in self.rows:
            print(f"[{s:<5}] {i}" + (f" — {d}" if d else ""))
        c = {k: sum(1 for r in self.rows if r[0] == k) for k in ("PASS", "FAIL", "WARN", "SKIP", "INFO")}
        print(f"\n요약: PASS {c['PASS']} / FAIL {c['FAIL']} / WARN {c['WARN']} / SKIP {c['SKIP']}")
        checked = c["PASS"] + c["FAIL"]
        if checked == 0 or c["PASS"] == 0:
            print("exit 2: 실제로 확인된 항목이 없습니다. 통과로 읽지 마세요.")
            return 2
        return 1 if c["FAIL"] else 0


def run(cmd, cwd=None, timeout=60):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return None, "없음"
    except subprocess.TimeoutExpired:
        return None, f"{timeout}초 초과"


def check_env(rep, root):
    v = sys.version_info
    rep.add("PASS" if v >= (3, 8) else "FAIL", "Python", f"{v.major}.{v.minor}.{v.micro} ({sys.executable})")
    have = [p for p in PACKAGES if importlib.util.find_spec(p)]
    missing = [p for p in PACKAGES if p not in have]
    rep.add("INFO", "설치된 패키지", ", ".join(have) or "없음")
    rep.add("INFO", "없는 패키지", ", ".join(missing) or "없음")
    if "pandas" not in have:
        rep.add("WARN", "pandas 없음", "csv 모듈이나 profile.py로 진행하거나 설치 가능 여부를 먼저 확인")
    for tool in ("git", "codex", "node", "pip", "uv"):
        path = shutil.which(tool)
        rep.add("INFO", f"CLI {tool}", path or "없음")
    try:
        fd, tmp = tempfile.mkstemp(dir=root)
        os.close(fd)
        os.remove(tmp)
        rep.add("PASS", "과제 폴더 쓰기 권한", root)
    except OSError as e:
        rep.add("WARN", "과제 폴더 쓰기 권한 없음", f"{e.__class__.__name__}: install.sh --user 사용")
    total, used, free = shutil.disk_usage(root)
    rep.add("INFO", "디스크 여유", f"{free / 2**30:.1f} GiB")
    now = datetime.now().astimezone()
    rep.add("INFO", "시스템 시간대", f"{now.tzname()} (UTC{now.strftime('%z')}) — 데이터 시각의 시간대와 비교")
    try:
        datetime.fromisoformat("2026-01-01T00:00:00Z")
        rep.add("INFO", "fromisoformat Z 접미사", "지원")
    except ValueError:
        rep.add("WARN", "fromisoformat Z 접미사", "미지원(Python 3.10 이하). 'Z'를 '+00:00'으로 바꿔 파싱")


def read_text(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def iter_files(root):
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            yield os.path.join(d, f)


def check_docs(rep, root):
    task = os.path.join(root, "TASK.md")
    if os.path.exists(task):
        text = read_text(task)
        if "Status: `TEMPLATE`" in text:
            rep.add("FAIL", "TASK.md", "Status가 아직 TEMPLATE")
        else:
            rep.add("PASS", "TASK.md", "계약 작성됨")
        states = re.findall(r"\|\s*(PASS|FAIL|NOT_RUN|HUMAN_CHECK)\s*\|", text)
        if states:
            bad = [s for s in states if s in ("FAIL", "NOT_RUN")]
            rep.add("WARN" if bad else "PASS", "완료 조건 상태",
                    f"{len(states)}개 중 FAIL/NOT_RUN {len(bad)}개" + (" → 한계로 기록했는지 확인" if bad else ""))
    else:
        rep.add("SKIP", "TASK.md", "없음 (과제가 다른 양식을 지정했으면 정상)")
    dec = os.path.join(root, "DECISIONS.md")
    if os.path.exists(dec):
        text = read_text(dec)
        filled = len(re.findall(r"^\|\s*D\d+\s*\|\s*[^|\s]", text, re.M))
        rep.add("PASS" if filled else "FAIL", "DECISIONS.md 결정 기록", f"{filled}건")
    else:
        rep.add("SKIP", "DECISIONS.md", "없음")
    own, other = [], []
    own_scanned = 0
    for f in iter_files(root):
        if f.endswith(".md"):
            rel = os.path.relpath(f, root)
            own_scanned += rel in KIT_DOCS
            for i, line in enumerate(read_text(f).splitlines(), 1):
                if PLACEHOLDER.search(line):
                    (own if rel in KIT_DOCS else other).append(f"{rel}:{i}")
    short = lambda h: ", ".join(h[:8]) + (f" 외 {len(h) - 8}건" if len(h) > 8 else "")
    if own:
        rep.add("FAIL", "기록 문서에 템플릿 문구 남음", short(own))
    elif not own_scanned:
        rep.add("SKIP", "기록 문서 템플릿 문구", "기록 문서 없음")
    else:
        rep.add("PASS", "기록 문서 템플릿 문구", "없음")
    if other:
        rep.add("WARN", "다른 문서의 TODO류 문구", short(other) + " — 과제 원본 문서면 무시")
    readme = os.path.join(root, "README.md")
    rep.add("PASS" if os.path.exists(readme) else "WARN", "README.md", "있음" if os.path.exists(readme) else "없음 (과제 제출 형식 확인)")


def find_tests(root):
    found = []
    for f in iter_files(root):
        b = os.path.basename(f)
        if b.endswith(".py") and (b.startswith("test_") or b.endswith("_test.py")):
            found.append(f)
    return found


def check_tests(rep, root, runner="auto"):
    tests = find_tests(root)
    if not tests:
        rep.add("FAIL", "테스트", "test_*.py가 없음. 완료 조건을 테스트로 옮겼는지 확인")
        return
    if runner == "pytest" or (runner == "auto" and importlib.util.find_spec("pytest")):
        code, out = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--ignore=.hk", "--ignore=.agents"], cwd=root, timeout=300)
        m = re.search(r"(\d+) passed", out or "")
        failed = re.search(r"(\d+) failed", out or "")
        skipped = re.search(r"(\d+) skipped", out or "")
        passed = int(m.group(1)) if m else 0
        if code == 0 and passed:
            rep.add("PASS", "pytest", f"{passed} passed" + (f", {skipped.group(1)} skipped" if skipped else ""))
        elif code == 5 or (code == 0 and not passed):
            rep.add("FAIL", "pytest", "실행된 테스트 0건 또는 전부 skip")
        else:
            last = (out or "").strip().splitlines()[-1:] or [""]
            rep.add("FAIL", "pytest", (failed.group(0) if failed else f"exit {code}") + f" — {last[0][:120]}")
        return
    dirs = sorted({os.path.relpath(os.path.dirname(t), root) for t in tests})
    total = 0
    for d in dirs:
        code, out = run([sys.executable, "-m", "unittest", "discover", "-s", d, "-p", "test*.py"], cwd=root, timeout=300)
        m = re.search(r"Ran (\d+) test", out or "")
        ran = int(m.group(1)) if m else 0
        sk = re.search(r"skipped=(\d+)", out or "")
        skipped = int(sk.group(1)) if sk else 0
        total += ran
        if code == 0 and ran > skipped:
            rep.add("PASS", f"unittest {d}", f"Ran {ran}" + (f", skipped {skipped}" if skipped else ""))
        elif code == 0:
            rep.add("FAIL", f"unittest {d}", "실행 0건 또는 전부 skip")
        else:
            rep.add("FAIL", f"unittest {d}", f"exit {code} — " + ((out or "").strip().splitlines()[-1:] or [""])[0][:120])
    if total == 0:
        rep.add("FAIL", "테스트", "unittest가 테스트를 하나도 찾지 못함 (pytest 스타일이면 pytest 설치 여부 확인)")


def check_secrets(rep, root):
    scanned = 0
    hits = []
    for f in iter_files(root):
        ext = os.path.splitext(f)[1].lower()
        if ext not in TEXT_EXT and not os.path.basename(f).startswith(".env"):
            continue
        try:
            if os.path.getsize(f) > 5_000_000:
                continue
            with open(f, encoding="utf-8", errors="ignore") as fh:
                for i, line in enumerate(fh, 1):
                    if SECRET.search(line):
                        hits.append(f"{os.path.relpath(f, root)}:{i}")
        except OSError:
            continue
        scanned += 1
    if scanned == 0:
        rep.add("SKIP", "비밀값 스캔", "스캔한 파일 0개")
    elif hits:
        rep.add("FAIL", "비밀값 의심", ", ".join(hits[:5]))
    else:
        rep.add("PASS", "비밀값 스캔", f"{scanned}개 파일, 발견 없음")


def check_git(rep, root):
    code, out = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root)
    if code != 0:
        rep.add("WARN", "git", "저장소가 아님. 작업 이력(git log)이 평가에 쓰이므로 과제 안내를 확인하고 git init 고려")
        return
    code, out = run(["git", "status", "--porcelain"], cwd=root)
    dirty = [l for l in (out or "").splitlines() if l.strip()]
    rep.add("WARN" if dirty else "PASS", "git 커밋 상태", f"커밋 안 된 변경 {len(dirty)}개" if dirty else "모두 커밋됨")
    code, out = run(["git", "rev-list", "--count", "HEAD"], cwd=root)
    n = int(out.strip()) if code == 0 and out.strip().isdigit() else 0
    rep.add("PASS" if n >= 3 else "WARN", "git 커밋 수", f"{n}개" + ("" if n >= 3 else " (단계별 커밋이 작업 과정의 증거가 됨)"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--env", action="store_true")
    ap.add_argument("--no-tests", action="store_true")
    ap.add_argument("--runner", choices=["auto", "pytest", "unittest"], default="auto")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    if not os.path.isdir(root):
        print(f"폴더가 없습니다: {root}")
        return 2
    rep = Report()
    if a.env:
        print(f"# 환경 점검: {root}\n")
        check_env(rep, root)
        rep.print()
        return 0
    print(f"# 제출 전 점검: {root}\n")
    check_docs(rep, root)
    if a.no_tests:
        rep.add("SKIP", "테스트", "--no-tests")
    else:
        check_tests(rep, root, a.runner)
    check_secrets(rep, root)
    check_git(rep, root)
    return rep.print()


if __name__ == "__main__":
    sys.exit(main())
