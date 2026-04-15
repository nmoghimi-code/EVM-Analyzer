from pathlib import Path
import unittest

from evm_xer_analyzer.analysis import analyze_schedules


class AnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.baseline = root / "test" / "archive (1)" / "UP33-54074-2026.01.16 - IPR.xer"
        self.current = root / "test" / "archive (1)" / "UP33-54074-2026.04.15 - IPR.xer"

    def test_analysis_returns_rows_for_matching_wbs(self) -> None:
        rows, baseline_schedule, current_schedule = analyze_schedules(
            self.baseline,
            self.current,
            ["interior"],
        )

        self.assertTrue(rows)
        self.assertEqual(len(rows), 1)
        self.assertEqual(baseline_schedule.project.data_date.year, 2026)
        self.assertEqual(current_schedule.project.data_date.year, 2026)
        self.assertTrue(any("INTERIOR" in row.matched_wbs_name.upper() for row in rows))
        self.assertTrue(any(row.baseline_task_count > 0 and row.current_task_count > 0 for row in rows))
        self.assertTrue(all(row.spi is None or row.spi >= 0 for row in rows))
        self.assertTrue(all(row.current_remaining_span_days >= 0 for row in rows))

    def test_analysis_requires_search_terms(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least one WBS search term"):
            analyze_schedules(self.baseline, self.current, [])


if __name__ == "__main__":
    unittest.main()
