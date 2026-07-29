import json, sys, unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.codegraph_check import (
    parse_block, partition_callers, check_symbol, impact_for_file, main,
)


def _cp(payload):
    """Fake CompletedProcess: JSON auf stdout, leerer stderr, rc 0."""
    m = MagicMock()
    m.stdout = json.dumps(payload)
    m.stderr = ""
    m.returncode = 0
    return m


class TestParseBlock(unittest.TestCase):
    def test_extracts_symbols_and_files(self):
        text = (
            "# Plan\n<!-- codegraph-check\n"
            "  symbols: init_db, upsert_job_score, mark_expired\n"
            "  files: jobscanner/storage.py, jobscanner/scanner.py -->\nrest\n"
        )
        syms, files = parse_block(text)
        self.assertEqual(syms, ["init_db", "upsert_job_score", "mark_expired"])
        self.assertEqual(files, ["jobscanner/storage.py", "jobscanner/scanner.py"])

    def test_missing_block_returns_none(self):
        self.assertEqual(parse_block("# Plan\nno block here\n"), (None, None))


class TestPartitionCallers(unittest.TestCase):
    def test_splits_by_is_test(self):
        results = [
            {"name": "score_profile_deterministic", "is_test": False},
            {"name": "push_batch_data", "is_test": False},
            {"name": "test_scores_missing", "is_test": True},
        ]
        callers, tests = partition_callers(results)
        self.assertEqual(callers, ["score_profile_deterministic", "push_batch_data"])
        self.assertEqual(tests, ["test_scores_missing"])


class TestCheckSymbol(unittest.TestCase):
    @patch("scripts.codegraph_check.subprocess.run")
    def test_ok_status_exists(self, run):
        run.return_value = _cp({"status": "ok", "results": [
            {"name": "caller_a", "is_test": False},
            {"name": "test_a", "is_test": True},
        ]})
        exists, callers, tests = check_symbol("/repo", "upsert_job_score")
        self.assertTrue(exists)
        self.assertEqual(callers, ["caller_a"])
        self.assertEqual(tests, ["test_a"])

    @patch("scripts.codegraph_check.subprocess.run")
    def test_ambiguous_status_exists(self, run):
        run.return_value = _cp({"status": "ambiguous", "candidates": [{}, {}]})
        exists, callers, tests = check_symbol("/repo", "init_db")
        self.assertTrue(exists)            # ambiguous zählt als existiert
        self.assertEqual((callers, tests), ([], []))

    @patch("scripts.codegraph_check.subprocess.run")
    def test_not_found_is_invented(self, run):
        run.return_value = _cp({"status": "not_found"})
        exists, _, _ = check_symbol("/repo", "save_score")
        self.assertFalse(exists)


class TestImpactForFile(unittest.TestCase):
    @patch("scripts.codegraph_check.subprocess.run")
    def test_returns_impact_summary(self, run):
        run.return_value = _cp({
            "status": "ok", "total_impacted": 852,
            "impacted_files": ["a.py", "b.py"],
        })
        summ = impact_for_file("/repo", "jobscanner/storage.py")
        self.assertEqual(summ["total_impacted"], 852)
        self.assertEqual(summ["impacted_file_count"], 2)


class TestMainGate(unittest.TestCase):
    def _plan(self, tmp_path, symbols, files):
        p = tmp_path / "draft.md"
        p.write_text(
            "# Draft\n<!-- codegraph-check\n"
            f"  symbols: {', '.join(symbols)}\n"
            f"  files: {', '.join(files)} -->\n",
            encoding="utf-8",
        )
        return str(p)

    @patch("scripts.codegraph_check._rebuild")
    @patch("scripts.codegraph_check.subprocess.run")
    def test_all_known_exit_0(self, run, _rb):
        # jeder query-Call: ok; jeder impact-Call: summary
        def side(args, **kw):
            if "impact" in args:
                return _cp({"status": "ok", "total_impacted": 3, "impacted_files": ["x.py"]})
            return _cp({"status": "ok", "results": [{"name": "c", "is_test": False}]})
        run.side_effect = side
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            plan = self._plan(Path(d), ["upsert_job_score"], ["jobscanner/storage.py"])
            rc = main(["--repo", "/opt/jobscanner", "--plan", plan])
        self.assertEqual(rc, 0)

    @patch("scripts.codegraph_check._rebuild")
    @patch("scripts.codegraph_check.subprocess.run")
    def test_invented_symbol_exit_1(self, run, _rb):
        def side(args, **kw):
            if "impact" in args:
                return _cp({"status": "ok", "total_impacted": 0, "impacted_files": []})
            sym = args[args.index("callers_of") + 1]
            if sym == "save_score":
                return _cp({"status": "not_found"})
            return _cp({"status": "ok", "results": []})
        run.side_effect = side
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            plan = self._plan(Path(d), ["upsert_job_score", "save_score"], ["jobscanner/storage.py"])
            rc = main(["--repo", "/opt/jobscanner", "--plan", plan])
        self.assertEqual(rc, 1)

    @patch("scripts.codegraph_check._rebuild")
    def test_missing_block_exit_1(self, _rb):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "draft.md"; p.write_text("# no block\n", encoding="utf-8")
            rc = main(["--repo", "/opt/jobscanner", "--plan", str(p)])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
