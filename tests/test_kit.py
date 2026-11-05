"""hynix-ai-kit 자체 테스트. 실행: python3 -m unittest discover -s tests -v"""
import contextlib
import csv
import importlib.util
import io
import os
import random
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
def load(name):
    spec = importlib.util.spec_from_file_location(f"hk_{name}", os.path.join(TOOLS, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


metrics = load("metrics")
preflight = load("preflight")
kitprofile = load("profile")   # 표준 라이브러리 profile 모듈과 이름이 겹쳐 경로로 직접 읽는다


def write_csv(path, header, rows, encoding="utf-8"):
    with open(path, "w", newline="", encoding=encoding) as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def capture(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn(*a)
    return code, buf.getvalue()


class TestProfile(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_detects_leak_column_and_key_duplicates(self):
        rnd = random.Random(0)
        rows = []
        for i in range(400):
            y = 1 if rnd.random() < 0.1 else 0
            rows.append([f"L{i // 25:03d}", f"{i % 25:02d}", f"{rnd.gauss(0, 1):.3f}",
                         f"{(5 + rnd.random()) if y else rnd.random():.3f}", "" if (y and i % 3 == 0) else f"{rnd.random():.2f}", y])
        rows.append(rows[0])  # 완전 중복 1행
        p = os.path.join(self.d, "d.csv")
        write_csv(p, ["lot_id", "wafer_id", "sensor_a", "cd_post_measure", "sensor_b", "label"], rows)
        code, out = capture(kitprofile.main, [p, "--target", "label", "--key", "lot_id,wafer_id"])
        self.assertEqual(code, 0)
        self.assertIn("행 401", out)
        self.assertIn("완전 중복 행: 1", out)
        self.assertRegex(out, r"cd_post_measure .*단일컬럼 AUC 1\.000 누수\?")
        self.assertNotRegex(out, r"\| sensor_a [^\n]*누수")
        self.assertIn("문자열로 읽기", out)            # wafer_id 앞자리 0
        self.assertIn("중복 키 1개", out)
        self.assertIn("결측행 양성률", out)            # sensor_b 결측이 양성에 몰림

    def test_join_explosion(self):
        a = os.path.join(self.d, "a.csv")
        b = os.path.join(self.d, "b.csv")
        write_csv(a, ["lot_id", "wafer_id", "y"], [["L1", "1", 1], ["L1", "2", 0], ["L2", "1", 0]])
        write_csv(b, ["lot_id", "step", "v"], [["L1", "s1", 1], ["L1", "s2", 2], ["L2", "s1", 3]])
        code, out = capture(kitprofile.main, ["join", a, b, "--on", "lot_id"])
        self.assertEqual(code, 0)
        self.assertIn("inner join 결과 5행", out)
        self.assertIn("1.67배", out)

    def test_cp949_and_empty(self):
        p = os.path.join(self.d, "k.csv")
        write_csv(p, ["설비", "값"], [["식각", "1"], ["증착", "2"]], encoding="cp949")
        code, out = capture(kitprofile.main, [p])
        self.assertIn("cp949", out)
        e = os.path.join(self.d, "e.csv")
        write_csv(e, ["a"], [])
        code, out = capture(kitprofile.main, [e])
        self.assertIn("데이터 행이 없습니다", out)


class TestMetrics(unittest.TestCase):
    Y = [1, 0, 1, 1, 0, 0, 1, 0, 0, 0]
    S = [0.9, 0.8, 0.7, 0.6, 0.55, 0.5, 0.4, 0.3, 0.2, 0.1]

    def test_hand_computed(self):
        p = [1 if s >= 0.5 else 0 for s in self.S]
        r = metrics.classification_report(self.Y, p)
        self.assertEqual((r["TP"], r["FP"], r["FN"], r["TN"]), (3, 3, 1, 3))
        self.assertAlmostEqual(r["precision"], 0.5)
        self.assertAlmostEqual(r["recall"], 0.75)
        self.assertAlmostEqual(r["f1"], 0.6)
        self.assertAlmostEqual(metrics.roc_auc(self.Y, self.S), 19 / 24)
        rec, cnt, ties = metrics.recall_at_k(self.Y, self.S, 0.3)
        self.assertEqual(cnt, 3)
        self.assertAlmostEqual(rec, 0.5)

    def test_zero_denominator(self):
        r = metrics.classification_report([0, 0], [0, 0])
        self.assertIsNone(r["precision"])
        self.assertIsNone(metrics.roc_auc([0, 0], [0.1, 0.2]))
        groups, total = metrics.weighted_yield([("A", 0, 0), ("B", 8, 10)])
        self.assertIsNone(groups["A"][2])
        self.assertAlmostEqual(total[2], 0.8)

    def test_weighted_yield_is_not_mean_of_ratios(self):
        groups, total = metrics.weighted_yield([("T", 99, 100), ("T", 1, 2)])
        self.assertAlmostEqual(total[2], 100 / 102)   # 행별 평균이면 0.745

    @unittest.skipUnless(importlib.util.find_spec("sklearn"), "sklearn 없음")
    def test_matches_sklearn(self):
        from sklearn.metrics import average_precision_score, roc_auc_score
        rnd = random.Random(1)
        y = [1 if rnd.random() < 0.2 else 0 for _ in range(500)]
        s = [round(rnd.random() + 0.3 * t, 2) for t in y]   # 동점 포함
        self.assertAlmostEqual(metrics.roc_auc(y, s), roc_auc_score(y, s), places=10)
        self.assertAlmostEqual(metrics.average_precision(y, s), average_precision_score(y, s), places=10)


class TestPreflight(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_empty_folder_is_not_pass(self):
        code, out = capture(preflight.main, ["--root", self.d])
        self.assertEqual(code, 2)
        self.assertIn("통과로 읽지 마세요", out)

    def test_template_left_and_secret_fail(self):
        shutil.copy(os.path.join(ROOT, "templates", "TASK.md"), self.d)
        with open(os.path.join(self.d, "app.py"), "w") as f:
            f.write('API_KEY = "abcdefghijklmnop"\n')
        os.makedirs(os.path.join(self.d, "tests"))
        with open(os.path.join(self.d, "tests", "test_a.py"), "w") as f:
            f.write("import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n        self.assertTrue(True)\n")
        code, out = capture(preflight.main, ["--root", self.d])
        self.assertEqual(code, 1)
        self.assertIn("Status가 아직 TEMPLATE", out)
        self.assertIn("비밀값 의심", out)
        self.assertRegex(out, r"\[PASS \] (pytest|unittest)")

    def test_unittest_runner_without_init_imports_project(self):
        os.makedirs(os.path.join(self.d, "src"))
        os.makedirs(os.path.join(self.d, "tests"))
        with open(os.path.join(self.d, "src", "mod.py"), "w") as f:
            f.write("def f():\n    return 1\n")
        with open(os.path.join(self.d, "tests", "test_m.py"), "w") as f:
            f.write("import unittest\nfrom src.mod import f\nclass T(unittest.TestCase):\n    def test_f(self):\n        self.assertEqual(f(), 1)\n")
        code, out = capture(preflight.main, ["--root", self.d, "--runner", "unittest"])
        self.assertIn("[PASS ] unittest tests", out)

    def test_all_skipped_tests_fail(self):
        with open(os.path.join(self.d, "test_s.py"), "w") as f:
            f.write("import unittest\nclass T(unittest.TestCase):\n    @unittest.skip('x')\n    def test_x(self):\n        pass\n")
        code, out = capture(preflight.main, ["--root", self.d])
        self.assertRegex(out, r"\[FAIL \] (pytest|unittest).*(skip|0건)")


class TestInstall(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.home = tempfile.mkdtemp()
        self.env = dict(os.environ, HOME=self.home)

    def tearDown(self):
        for p in (self.d, self.home):
            os.chmod(p, 0o755)
            shutil.rmtree(p, ignore_errors=True)

    def sh(self, *args, cwd=None):
        return subprocess.run(["bash", os.path.join(ROOT, "install.sh"), *args], cwd=cwd or self.d,
                              capture_output=True, text=True, env=self.env)

    def test_project_install_preserves_existing_agents(self):
        with open(os.path.join(self.d, "AGENTS.md"), "w") as f:
            f.write("# 과제 원래 지침\n출력은 result.csv\n")
        r = self.sh()
        self.assertEqual(r.returncode, 0, r.stderr)
        text = open(os.path.join(self.d, "AGENTS.md")).read()
        self.assertTrue(text.startswith("# 과제 원래 지침"))
        self.assertEqual(text.count("hynix-ai-kit:begin"), 1)
        r2 = self.sh()   # 재설치해도 블록이 하나
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertEqual(open(os.path.join(self.d, "AGENTS.md")).read().count("hynix-ai-kit:begin"), 1)
        for s in ("hk-start", "hk-data", "hk-design", "hk-build", "hk-verify", "hk-handoff", "hk-wrap"):
            self.assertTrue(os.path.exists(os.path.join(self.d, ".agents", "skills", s, "SKILL.md")))
        self.assertTrue(os.path.exists(os.path.join(self.d, "TASK.md")))
        self.assertTrue(os.path.exists(os.path.join(self.d, ".hk", "AGENTS.md.orig")))
        self.assertEqual(self.sh("--check").returncode, 0)

    def test_readonly_folder_points_to_user_mode(self):
        if os.geteuid() == 0:
            self.skipTest("root는 권한 제한을 무시함")
        os.chmod(self.d, stat.S_IRUSR | stat.S_IXUSR)
        r = self.sh()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--user", r.stderr)

    def test_user_install_does_not_touch_task(self):
        r = self.sh("--user")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.listdir(self.d), [])
        self.assertTrue(os.path.exists(os.path.join(self.home, ".agents", "skills", "hk-data", "SKILL.md")))
        self.assertTrue(os.path.exists(os.path.join(self.home, ".agents", "hynix-ai-kit", "tools", "preflight.py")))
        self.assertEqual(self.sh("--check", "--user").returncode, 0)

    def test_conflicting_skill_stops(self):
        dst = os.path.join(self.d, ".agents", "skills", "hk-data")
        os.makedirs(dst)
        with open(os.path.join(dst, "SKILL.md"), "w") as f:
            f.write("다른 내용")
        r = self.sh()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--force", r.stderr)


class TestDocs(unittest.TestCase):
    def test_skill_frontmatter(self):
        base = os.path.join(ROOT, ".agents", "skills")
        names = sorted(os.listdir(base))
        self.assertEqual(names, ["hk-build", "hk-data", "hk-design", "hk-handoff", "hk-start", "hk-verify", "hk-wrap"])
        for n in names:
            text = open(os.path.join(base, n, "SKILL.md"), encoding="utf-8").read()
            self.assertTrue(text.startswith(f"---\nname: {n}\ndescription: "), n)
            desc = text.split("description: ", 1)[1].split("\n", 1)[0]
            self.assertLess(len(desc), 1024, n)

    def test_referenced_tools_exist(self):
        import re
        for d, _, files in os.walk(ROOT):
            if ".git" in d:
                continue
            for f in files:
                if f.endswith(".md"):
                    for m in re.findall(r"\.hk/tools/(\w+\.py)", open(os.path.join(d, f), encoding="utf-8").read()):
                        self.assertTrue(os.path.exists(os.path.join(TOOLS, m)), f"{f}: {m}")


if __name__ == "__main__":
    unittest.main()


class TestPractice(unittest.TestCase):
    """모의 과제 생성기와 채점기가 끝까지 실행되고, 기준선이 함정에 걸리는지 확인한다."""

    def run_py(self, script, *args, cwd):
        return subprocess.run([sys.executable, os.path.join(ROOT, "practice", script), *args],
                              cwd=cwd, capture_output=True, text=True)

    def test_p3_baseline_violates_hidden_pm(self):
        d = tempfile.mkdtemp()
        try:
            self.assertEqual(self.run_py("p3-metrology-dispatch/make_data.py", cwd=d).returncode, 0)
            self.assertEqual(self.run_py("p3-metrology-dispatch/grade.py", "--baseline", "b.csv", cwd=d).returncode, 0)
            r = self.run_py("p3-metrology-dispatch/grade.py", "b.csv", cwd=d)
            self.assertEqual(r.returncode, 1)
            self.assertIn("정비 시간 배정", r.stdout)
        finally:
            shutil.rmtree(d)

    def test_p1_p2_generate_and_reject_bad_submission(self):
        for task, bad in (("p1-etch-screening", "lot_id,wafer_id,score,screen\nX,01,1,1\n"),
                          ("p2-alarm-triage", "rank,equipment_id,alarm_code,first_time,last_time,count,reason\n1,ETCH-01,E-101,2026-10-19 00:00,2026-10-19 00:00,1,\n")):
            d = tempfile.mkdtemp()
            try:
                self.assertEqual(self.run_py(f"{task}/make_data.py", cwd=d).returncode, 0)
                with open(os.path.join(d, "s.csv"), "w") as f:
                    f.write(bad)
                self.assertEqual(self.run_py(f"{task}/grade.py", "s.csv", cwd=d).returncode, 1, task)
            finally:
                shutil.rmtree(d)
