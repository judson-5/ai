import csv
import tempfile
import unittest
from pathlib import Path

from agents.csv_report import build_reports, HISTORY_FIELDS, PROP_FIELDS


class CsvReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.history = Path(self.temp.name) / "history.csv"
        self.props = Path(self.temp.name) / "props.csv"
        self.write(self.history, HISTORY_FIELDS, [["Test", "2026-01-01", "points", 11],
                                                ["Test", "2026-01-03", "points", 0]])
        self.write(self.props, PROP_FIELDS, [["Test", "points", 10.5, "over", 1.9, "2026-01-03"]])

    def write(self, path, fields, rows):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(fields)
            writer.writerows(rows)

    def test_cutoff_excludes_same_day_and_future(self):
        report = build_reports(self.history, self.props)[0]
        self.assertEqual(report["sample_size"], 1)
        self.assertEqual(report["average"], 11)
        self.assertFalse(report["qualifies"])

    def test_nonfinite_rejected(self):
        for value in ["nan", "inf", "-inf"]:
            self.write(self.history, HISTORY_FIELDS, [["Test", "2026-01-01", "points", value]])
            with self.assertRaises(ValueError):
                build_reports(self.history, self.props)

    def test_duplicates_rejected(self):
        row = ["Test", "2026-01-01", "points", 11]
        self.write(self.history, HISTORY_FIELDS, [row, row])
        with self.assertRaises(ValueError):
            build_reports(self.history, self.props)

    def test_missing_history_rejected(self):
        self.write(self.props, PROP_FIELDS, [["Other", "points", 10.5, "over", 1.9, "2026-01-03"]])
        with self.assertRaises(ValueError):
            build_reports(self.history, self.props)

    def test_bad_schema_and_incomplete_rows_rejected(self):
        for text in ["wrong,headers\na,b\n", "player,game_date,market,value\nTest,2026-01-01,points\n"]:
            self.history.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                build_reports(self.history, self.props)
