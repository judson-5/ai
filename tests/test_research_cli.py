"""End-to-end CLI orchestration with synthetic provider responses, no network."""
import contextlib
import io
import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from paper_trading.cli import main
from test_paper_research import NOW, bars, option, capture


class CliTests(TestCase):
    def invoke(self, args, now=NOW):
        output = io.StringIO()
        with patch("sys.argv", ["paper-research", *args]), patch("paper_trading.cli.utcnow", return_value=now), contextlib.redirect_stdout(output):
            main()
        return json.loads(output.getvalue())

    def test_capture_persistent_paper_fill_and_current_quote_close(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            args = ["analyze", "SPY", "--option-feed", "opra", "--paper", "--trade-id", "one",
                    "--ledger", str(path/"paper.sqlite3"), "--capture", str(path/"first.json")]
            with patch("paper_trading.cli.AlpacaData") as data:
                data.return_value.bars.return_value = bars()
                data.return_value.options.return_value = [option()]
                result = self.invoke(args)
                self.assertEqual(result["paper_fills"][0]["id"], "one")
            self.assertEqual(json.loads((path/"first.json").read_text())["source"], "alpaca")
            status = self.invoke(["status", "--ledger", str(path/"paper.sqlite3")])
            self.assertIsNone(status["positions"][0]["closed"])
            later = capture()
            later["frames"] = later["frames"][1:]
            (path/"exit.json").write_text(json.dumps(later))
            from datetime import timedelta
            closed = self.invoke(["close", "one", str(path/"exit.json"), "--ledger", str(path/"paper.sqlite3")], NOW+timedelta(minutes=5))
            self.assertAlmostEqual(closed["realized_pnl"], 1.7)

    def test_merge_to_backtest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            payload = capture()
            for i, frame in enumerate(payload["frames"]):
                (path/f"{i}.json").write_text(json.dumps({**payload, "frames": [frame]}))
            result = self.invoke(["merge-captures", str(path/"1.json"), str(path/"0.json"),
                                  "--output", str(path/"merged.json")])
            self.assertEqual(result["frames"], 2)
            report = self.invoke(["backtest", str(path/"merged.json")])
            self.assertEqual(report["closed_trades"], 1)

    def test_indicative_paper_fill_rejected_before_provider_call(self):
        with patch("paper_trading.cli.AlpacaData") as data, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exit_code:
                self.invoke(["analyze", "SPY", "--paper"])
            self.assertEqual(exit_code.exception.code, 2)
            data.assert_not_called()
