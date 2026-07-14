from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wechat_decrypt_tool import wcdb_realtime


class TestWCDBRealtimeMessageTimeRange(unittest.TestCase):
    def test_get_messages_by_time_builds_expected_sql(self):
        captured = {}

        def _fake_exec_query(handle, *, kind, path, sql):
            captured["handle"] = handle
            captured["kind"] = kind
            captured["path"] = path
            captured["sql"] = sql
            return [{"local_id": 1, "sender_username": "wxid_abc"}]

        with (
            patch.object(wcdb_realtime, "_ensure_initialized"),
            patch.object(wcdb_realtime, "exec_query", side_effect=_fake_exec_query),
        ):
            rows = wcdb_realtime.get_messages_by_time(
                7,
                "wxid_friend",
                db_path="C:/tmp/message_0.db",
                start_time=100,
                end_time=200,
                limit=300,
                offset=10,
            )

        self.assertEqual(rows, [{"local_id": 1, "sender_username": "wxid_abc"}])
        self.assertEqual(captured["handle"], 7)
        self.assertEqual(captured["kind"], "message")
        self.assertEqual(captured["path"], "C:/tmp/message_0.db")
        self.assertIn('FROM "msg_', captured["sql"])
        self.assertIn('LEFT JOIN Name2Id AS n ON n.rowid = m.real_sender_id', captured["sql"])
        self.assertIn('m.create_time >= 100 AND m.create_time < 200', captured["sql"])
        self.assertIn('LIMIT 300 OFFSET 10', captured["sql"])
        self.assertIn('ORDER BY m.create_time ASC', captured["sql"])

    def test_get_messages_by_time_empty_username(self):
        with patch.object(wcdb_realtime, "_ensure_initialized"):
            rows = wcdb_realtime.get_messages_by_time(
                1,
                "",
                db_path="C:/tmp/message_0.db",
                start_time=1,
                end_time=2,
            )
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
