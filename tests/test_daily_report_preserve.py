"""Test that manual entries are preserved on regeneration."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path


class TestDailyReportPreserveManual(unittest.TestCase):
    """Verify that generate_daily_report preserves manual entries.

    Instead of importing the real module (which triggers heavy imports),
    we test the filtering logic in isolation.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reports_dir = Path(self.tmp.name) / "daily_reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _save(self, date_str: str, data: dict):
        p = self.reports_dir / f"{date_str}.json"
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self, date_str: str) -> dict | None:
        p = self.reports_dir / f"{date_str}.json"
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def _preserve_custom_entries(self, date_str: str, new_entries: list[dict]) -> list[dict]:
        """Simulates the exact logic from daily_report_service.py."""
        old = self._load(date_str)
        if old:
            custom = [
                e for e in old.get("entries", [])
                if e.get("_is_manual") or not e.get("username")
            ]
            if custom:
                new_entries.extend(custom)
        return new_entries

    def test_old_llm_entries_are_replaced(self):
        """LLM-generated entries (non-empty username, no _is_manual) should be replaced."""
        self._save("2026-06-20", {
            "entries": [
                {"username": "wxid_old", "display_name": "旧客户", "summary": "老数据"},
                {"username": "", "display_name": "手工", "summary": "手工登记"},
            ]
        })
        new = [
            {"username": "wxid_new", "display_name": "新客户", "summary": "新数据"},
        ]
        result = self._preserve_custom_entries("2026-06-20", new)
        usernames = [e["username"] for e in result]
        self.assertIn("wxid_new", usernames)    # new LLM entry
        self.assertNotIn("wxid_old", usernames)  # old LLM entry removed
        self.assertIn("", usernames)              # manual entry preserved

    def test_manual_entry_with_flag_preserved(self):
        """Entry with _is_manual flag should be preserved."""
        self._save("2026-06-21", {
            "entries": [
                {"username": "wxid_foo", "display_name": "Foo", "summary": "done"},
                {"_is_manual": True, "username": "wxid_manual", "display_name": "手工", "summary": "自填"},
            ]
        })
        new = [{"username": "wxid_new", "display_name": "New", "summary": "new"}]
        result = self._preserve_custom_entries("2026-06-21", new)
        usernames = [e["username"] for e in result]
        self.assertIn("wxid_new", usernames)
        self.assertNotIn("wxid_foo", usernames)
        # wxid_manual has _is_manual=True even though username is set
        self.assertIn("wxid_manual", usernames)

    def test_no_old_report(self):
        """No existing report → no preservation."""
        new = [{"username": "wxid_new", "summary": "new"}]
        result = self._preserve_custom_entries("2026-06-22", new)
        self.assertEqual(len(result), 1)

    def test_empty_custom_list(self):
        """No custom entries in old report → no extras appended."""
        self._save("2026-06-23", {
            "entries": [
                {"username": "wxid_a", "summary": "a"},
                {"username": "wxid_b", "summary": "b"},
            ]
        })
        new = [{"username": "wxid_new", "summary": "new"}]
        result = self._preserve_custom_entries("2026-06-23", new)
        self.assertEqual(len(result), 1)

    def test_mixed_preservation_order(self):
        """Custom entries go AFTER new entries."""
        self._save("2026-06-24", {
            "entries": [
                {"username": "wxid_old", "summary": "old"},
                {"_is_manual": True, "username": "", "summary": "manual1"},
                {"username": "", "summary": "manual2"},
            ]
        })
        new = [{"username": "wxid_new", "summary": "new"}]
        result = self._preserve_custom_entries("2026-06-24", new)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["username"], "wxid_new")
        self.assertEqual(result[1]["summary"], "manual1")
        self.assertEqual(result[2]["summary"], "manual2")


if __name__ == "__main__":
    unittest.main()
