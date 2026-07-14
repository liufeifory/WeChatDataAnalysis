from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx

from .app_paths import get_output_dir
from .chat_helpers import (
    _decode_message_content,
    _extract_sender_from_group_xml,
    _iter_message_db_paths,
    _list_decrypted_accounts,
    _load_contact_rows,
    _pick_display_name,
    _resolve_account_dir,
    _resolve_msg_table_name,
    _should_keep_session,
    _split_group_sender_prefix,
)
from .logging_config import get_logger
from .wcdb_realtime import (
    WCDB_REALTIME,
    WCDBRealtimeError,
    get_display_names,
    get_messages,
    get_messages_by_time,
    get_sessions,
)

logger = get_logger(__name__)


# ── helpers (same pattern as chat_realtime_autosync) ──────────────────────

def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "") or "").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


def _env_str(name: str, default: str) -> str:
    return str(os.environ.get(name, "") or "").strip() or default


def _env_int(name: str, default: int, *, min_v: int, max_v: int) -> int:
    raw = str(os.environ.get(name, "") or "").strip()
    try:
        v = int(raw)
    except Exception:
        v = int(default)
    if v < min_v:
        v = min_v
    if v > max_v:
        v = max_v
    return v


# ── config ────────────────────────────────────────────────────────────────

@dataclass
class DailyReportConfig:
    enabled: bool = True
    schedule_time: str = "18:00"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_max_tokens: int = 8192
    account: str | None = None


def _read_daily_report_config() -> DailyReportConfig:
    # Merge env vars + runtime settings.
    from .runtime_settings import read_effective_daily_report_llm_config

    merged = read_effective_daily_report_llm_config()

    enabled_raw = str(merged.get("enabled", "true") or "true").strip().lower()
    enabled = enabled_raw not in {"0", "false", "no", "off"}

    return DailyReportConfig(
        enabled=enabled,
        schedule_time=str(merged.get("schedule_time", "18:00") or "18:00").strip(),
        llm_base_url=str(merged.get("llm_base_url", "") or "").strip(),
        llm_api_key=str(merged.get("llm_api_key", "") or "").strip(),
        llm_model=str(merged.get("llm_model", "gpt-4o-mini") or "gpt-4o-mini").strip(),
        llm_max_tokens=_env_int("WECHAT_TOOL_DAILY_REPORT_LLM_MAX_TOKENS", 8192, min_v=256, max_v=64000),
        account=_env_str("WECHAT_TOOL_DAILY_REPORT_ACCOUNT", "") or None,
    )


# ── report I/O ────────────────────────────────────────────────────────────

def _get_reports_dir() -> Path:
    d = get_output_dir() / "daily_reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _report_path(date_str: str) -> Path:
    return _get_reports_dir() / f"{date_str}.json"


def _save_report(date_str: str, data: dict) -> None:
    path = _report_path(date_str)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_report(date_str: str) -> dict | None:
    path = _report_path(date_str)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("[daily-report] Corrupted report file: %s", path)
        return None


def _list_report_dates() -> list[str]:
    rd = _get_reports_dir()
    dates: list[str] = []
    if not rd.exists():
        return dates
    for p in sorted(rd.glob("*.json"), reverse=True):
        stem = p.stem
        if re.match(r"^\d{4}-\d{2}-\d{2}$", stem):
            dates.append(stem)
    return dates


# ── in-memory generation lock (prevents concurrent generation for same date) ──

_generating_lock: set[str] = set()


# ── local date helpers (mirrors routers/chat.py logic) ────────────────────

def _local_day_range_epoch_seconds(date_str: str) -> tuple[int, int, str]:
    d0 = datetime.strptime(str(date_str or "").strip(), "%Y-%m-%d")
    d1 = d0 + timedelta(days=1)
    return int(d0.timestamp()), int(d1.timestamp()), d0.strftime("%Y-%m-%d")


# ── message scanning ──────────────────────────────────────────────────────

def _load_session_usernames(contact_db_path: Path) -> list[str]:
    """Return all session usernames from session.db SessionTable."""
    session_db = contact_db_path.parent / "session.db"
    if not session_db.exists():
        return []
    try:
        conn = sqlite3.connect(str(session_db))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT username FROM SessionTable ORDER BY sort_timestamp DESC"
            ).fetchall()
            return [str(r["username"]) for r in rows if r["username"]]
        finally:
            conn.close()
    except Exception:
        logger.exception("[daily-report] Failed to read session.db")
        return []


def _get_my_rowid(account_dir: Path) -> int | None:
    """Get the user's own rowid from Name2Id in the first message db."""
    for db_path in _iter_message_db_paths(account_dir):
        try:
            conn = sqlite3.connect(str(db_path))
            try:
                account_name = account_dir.name
                rows = conn.execute(
                    "SELECT rowid FROM Name2Id WHERE user_name = ?", (account_name,)
                ).fetchall()
                if rows:
                    return int(rows[0][0])
            finally:
                conn.close()
        except Exception:
            continue
    return None


def _get_sender_username_map(account_dir: Path) -> dict[int, str]:
    """Build {rowid: username} mapping from Name2Id across all message DBs."""
    mapping: dict[int, str] = {}
    for db_path in _iter_message_db_paths(account_dir):
        try:
            conn = sqlite3.connect(str(db_path))
            try:
                rows = conn.execute("SELECT rowid, user_name FROM Name2Id").fetchall()
                for r in rows:
                    rid = int(r[0])
                    if rid not in mapping:
                        mapping[rid] = str(r[1] or "")
            finally:
                conn.close()
        except Exception:
            continue
    return mapping


_MATCHMAKING_PATTERNS = re.compile(r"相亲|交友|婚恋|约会|脱单|征友|找对象|征婚")


def _is_matchmaking_group(name: str) -> bool:
    return bool(_MATCHMAKING_PATTERNS.search(name))


def _diag_target_date() -> str:
    return _env_str("WECHAT_TOOL_DAILY_REPORT_DIAG_DATE", "")


def _diag_target_keyword() -> str:
    return _env_str("WECHAT_TOOL_DAILY_REPORT_DIAG_KEYWORD", "")


def _should_diag_conversation(date_str: str, username: str, display_name: str) -> bool:
    target_date = _diag_target_date()
    if target_date and target_date != str(date_str or "").strip():
        return False

    keyword = _diag_target_keyword().lower()
    if not keyword:
        return False

    return keyword in str(username or "").lower() or keyword in str(display_name or "").lower()


def _diag_log_summary(
    backend: str,
    outcome: str,
    date_str: str,
    username: str,
    display_name: str,
    metrics: dict[str, Any],
) -> None:
    logger.info(
        "[daily-report][diag][%s] outcome=%s date=%s username=%s display_name=%s metrics=%s",
        backend,
        outcome,
        date_str,
        username,
        display_name,
        metrics,
    )


def _diag_conversation_entry(date_str: str, entry: dict[str, Any]) -> bool:
    return _should_diag_conversation(
        date_str,
        str(entry.get("username") or ""),
        str(entry.get("display_name") or ""),
    )


def _collect_account_day_messages(account_dir: Path, date_str: str) -> list[dict]:
    """Scan one account's messages for a given day.

    Tries WCDB realtime first for fresh data, falls back to decrypted
    SQLite snapshots (which may be stale).
    """
    diag_enabled = bool(_diag_target_keyword()) and (
        not _diag_target_date() or _diag_target_date() == date_str
    )
    if diag_enabled:
        logger.info(
            "[daily-report][diag] start account=%s date=%s keyword=%s",
            account_dir.name,
            date_str,
            _diag_target_keyword(),
        )

    # Try WCDB realtime first (live data, not stale snapshots).
    try:
        conversations = _collect_account_day_messages_wcdb(account_dir, date_str)
        if diag_enabled:
            logger.info(
                "[daily-report][diag] backend=wcdb account=%s date=%s conversations=%d",
                account_dir.name,
                date_str,
                len(conversations),
            )
        return conversations
    except WCDBRealtimeError as exc:
        logger.debug("[daily-report] WCDB unavailable, fallback to SQLite: %s", exc)
        if diag_enabled:
            logger.info(
                "[daily-report][diag] backend=wcdb-unavailable account=%s date=%s error=%s",
                account_dir.name,
                date_str,
                exc,
            )
    except Exception:
        logger.exception("[daily-report] WCDB error, fallback to SQLite")
        if diag_enabled:
            logger.exception(
                "[daily-report][diag] backend=wcdb-error account=%s date=%s",
                account_dir.name,
                date_str,
            )

    conversations = _collect_account_day_messages_sqlite(account_dir, date_str)
    if diag_enabled:
        logger.info(
            "[daily-report][diag] backend=sqlite account=%s date=%s conversations=%d",
            account_dir.name,
            date_str,
            len(conversations),
        )
    return conversations


def _collect_account_day_messages_wcdb(account_dir: Path, date_str: str) -> list[dict]:
    """Scan messages via WCDB realtime (live data, not stale snapshots).

    Returns same format as _collect_account_day_messages_sqlite.
    """
    start_ts, end_ts, _ = _local_day_range_epoch_seconds(date_str)

    conn = WCDB_REALTIME.ensure_connected(account_dir)
    with conn.lock:
        raw_sessions = get_sessions(conn.handle)

    # Extract unique usernames from WCDB sessions.
    usernames: list[str] = []
    for item in raw_sessions:
        if not isinstance(item, dict):
            continue
        uname = str(
            item.get("username")
            or item.get("user_name")
            or item.get("UserName")
            or ""
        ).strip()
        if uname:
            usernames.append(uname)

    if not usernames:
        logger.info("[daily-report] WCDB: no sessions for %s", account_dir.name)
        return []

    # Batch-fetch all display names from WCDB (more complete than contact.db).
    with conn.lock:
        wcdb_names = get_display_names(conn.handle, usernames)

    # Helper: pick a value by multiple possible keys (handles camelCase/snake_case).
    def _pick(item: dict, *keys: str) -> Any:
        for k in keys:
            v = item.get(k)
            if v is not None:
                return v
        lk_lower = {str(kk).lower(): kk for kk in item}
        for k in keys:
            actual = lk_lower.get(k.lower())
            if actual is not None:
                return item.get(actual)
        return None

    conversations: list[dict] = []

    # Use the account's actual wxid to reliably detect sent messages.
    my_wxid = conn.native_wxid or ""

    for username in usernames:
        if not _should_keep_session(username, include_official=False):
            continue

        is_group = username.endswith("@chatroom")
        display_name = wcdb_names.get(username) or username
        diag = _should_diag_conversation(date_str, username, display_name)
        diag_metrics = {
            "raw_rows": 0,
            "in_range_rows": 0,
            "sender_nonempty": 0,
            "self_matches": 0,
            "decoded_nonempty": 0,
            "decoded_empty": 0,
            "final_rows": 0,
            "pages_fetched": 0,
        }
        diag_samples: list[dict[str, Any]] = []

        # Skip matchmaking groups.
        if is_group and _is_matchmaking_group(display_name):
            logger.info(
                "[daily-report] WCDB: skipping matchmaking group: %s (%s)",
                display_name, username,
            )
            if diag:
                _diag_log_summary(
                    "wcdb",
                    "skipped_matchmaking",
                    date_str,
                    username,
                    display_name,
                    {**diag_metrics, "native_wxid": my_wxid},
                )
            continue

        # Fetch messages for target day directly when possible.
        raw_rows: list[dict[str, Any]] = []
        try:
            msg_db_path = conn.db_storage_dir / "message" / "message_0.db"
            raw_rows = get_messages_by_time(
                conn.handle,
                username,
                db_path=msg_db_path,
                start_time=start_ts,
                end_time=end_ts,
                limit=2000,
                offset=0,
            )
            diag_metrics["pages_fetched"] = 1
        except Exception:
            logger.debug(
                "[daily-report] WCDB time-range query failed for %s, fallback to paging",
                username,
                exc_info=True,
            )
            # Fallback: WCDB returns newest-first, so for historical dates we
            # may need to page backward until we reach the target day instead of
            # looking only at the latest 200 rows.
            page_size = 200
            max_pages = 50
            saw_older_than_start = False
            for page in range(max_pages):
                diag_metrics["pages_fetched"] = page + 1
                with conn.lock:
                    batch = get_messages(
                        conn.handle,
                        username,
                        limit=page_size,
                        offset=page * page_size,
                    )
                if not batch:
                    break
                raw_rows.extend(batch)

                batch_oldest = None
                batch_has_target_day = False
                for item in batch:
                    if not isinstance(item, dict):
                        continue
                    create_time = int(_pick(item, "create_time", "createTime", "CreateTime") or 0)
                    if batch_oldest is None or (create_time and create_time < batch_oldest):
                        batch_oldest = create_time
                    if start_ts <= create_time < end_ts:
                        batch_has_target_day = True
                    if create_time and create_time < start_ts:
                        saw_older_than_start = True

                if saw_older_than_start and batch_has_target_day:
                    break
                if batch_oldest is not None and batch_oldest < start_ts and not batch_has_target_day:
                    break
                if len(batch) < page_size:
                    break
        diag_metrics["raw_rows"] = len(raw_rows)

        today_lines: list[tuple[int, str]] = []
        has_my_messages = False

        for item in raw_rows:
            if not isinstance(item, dict):
                continue

            create_time = int(_pick(item, "create_time", "createTime", "CreateTime") or 0)
            if create_time < start_ts or create_time >= end_ts:
                continue
            diag_metrics["in_range_rows"] += 1

            compress = _pick(item, "compress_content", "compressContent", "CompressContent")
            msg_content = _pick(item, "message_content", "messageContent", "MessageContent") or ""

            # Determine if this message was sent by the current user by comparing
            # senderUsername against the WCDB connection's native_wxid.
            # This is more reliable than the is_send/isSent field which may use
            # different naming depending on the WCDB API version.
            sender_username = str(
                _pick(item, "sender_username", "senderUsername", "sender", "SenderUsername") or ""
            )
            if sender_username:
                diag_metrics["sender_nonempty"] += 1
            is_sent = bool(my_wxid) and sender_username == my_wxid
            if is_sent:
                has_my_messages = True
                diag_metrics["self_matches"] += 1

            # Decode message content.
            raw = _decode_message_content(compress, msg_content)
            text = (raw or "").strip()
            if not text:
                diag_metrics["decoded_empty"] += 1
                continue
            diag_metrics["decoded_nonempty"] += 1

            alt_sender_prefix = ""
            alt_sender_xml = ""
            if is_group:
                alt_sender_prefix, _ = _split_group_sender_prefix(text, sender_username)
                if text.startswith("<") or text.startswith('"<'):
                    alt_sender_xml = _extract_sender_from_group_xml(text)
            if diag and len(diag_samples) < 8:
                diag_samples.append({
                    "ts": create_time,
                    "sender_username": sender_username,
                    "is_sent": is_sent,
                    "prefix_sender": alt_sender_prefix,
                    "xml_sender": alt_sender_xml,
                    "text_preview": text[:80],
                })

            if is_sent:
                sender_label = "我"
            elif is_group and sender_username:
                sender_label = wcdb_names.get(sender_username) or sender_username
            else:
                sender_label = display_name

            today_lines.append((create_time, f"{sender_label}: {text}"))

        if not has_my_messages:
            logger.info(
                "[daily-report] WCDB: skipping conversation with no replies: %s (%s)",
                display_name, username,
            )
            if diag:
                _diag_log_summary(
                    "wcdb",
                    "skipped_no_self_messages",
                    date_str,
                    username,
                    display_name,
                    {
                        **diag_metrics,
                        "native_wxid": my_wxid,
                        "samples": diag_samples,
                    },
                )
            continue

        # Sort chronologically (WCDB returns newest-first).
        today_lines.sort(key=lambda t: t[0])

        # Enforce limits.
        max_msgs = 100
        max_chars = 16000
        total = 0
        truncated: list[str] = []
        for _, line in today_lines[:max_msgs]:
            total += len(line) + 1
            if total > max_chars:
                break
            truncated.append(line)
        diag_metrics["final_rows"] = len(truncated)

        if truncated:
            conversations.append({
                "username": username,
                "display_name": display_name,
                "is_group": is_group,
                "messages": truncated,
            })
            logger.debug(
                "[daily-report] WCDB: collected %d msgs from %s (%s)",
                len(truncated), display_name, username,
            )
            if diag:
                _diag_log_summary(
                    "wcdb",
                    "included",
                    date_str,
                    username,
                    display_name,
                    {
                        **diag_metrics,
                        "native_wxid": my_wxid,
                        "samples": diag_samples,
                    },
                )
        elif diag:
            _diag_log_summary(
                "wcdb",
                "skipped_empty_after_decode",
                date_str,
                username,
                display_name,
                {
                    **diag_metrics,
                    "native_wxid": my_wxid,
                    "samples": diag_samples,
                },
            )

    logger.info("[daily-report] WCDB: %d conversations for %s", len(conversations), account_dir.name)
    return conversations


def _sqlite_sender_matches_self(
    *,
    account_name: str,
    my_rowid: int | None,
    sender_uid: int,
    sender_username: str,
    alt_sender_prefix: str,
    alt_sender_xml: str,
) -> bool:
    if my_rowid is not None and sender_uid == my_rowid:
        return True

    account_lower = str(account_name or "").strip().lower()
    candidates = {
        str(sender_username or "").strip().lower(),
        str(alt_sender_prefix or "").strip().lower(),
        str(alt_sender_xml or "").strip().lower(),
    }
    candidates.discard("")
    return bool(account_lower and account_lower in candidates)


    """Scan one account's messages from decrypted SQLite snapshots.

    This is the fallback path — snapshots may be stale. See
    _collect_account_day_messages_wcdb for the live-data path.

    Returns a list of conversation dicts:
        {
            "username": str,
            "display_name": str,
            "is_group": bool,
            "messages": ["sender: text", ...],
        }
    """
    start_ts, end_ts, _ = _local_day_range_epoch_seconds(date_str)
    contact_db_path = account_dir / "contact.db"

    # Preload contact info for display name resolution.
    session_usernames = _load_session_usernames(contact_db_path)
    if not session_usernames:
        logger.info("[daily-report] No sessions found in %s", account_dir)
        return []

    contact_rows = _load_contact_rows(contact_db_path, session_usernames)

    # Preload sender username mapping across all message DBs.
    sender_map = _get_sender_username_map(account_dir)
    my_rowid = _get_my_rowid(account_dir)

    # Collect message DB paths once (shared by all sessions).
    msg_db_paths = _iter_message_db_paths(account_dir)

    conversations: list[dict] = []

    for username in session_usernames:
        if not _should_keep_session(username, include_official=False):
            continue

        is_group = username.endswith("@chatroom")
        display_name = _pick_display_name(contact_rows.get(username), username)
        diag = _should_diag_conversation(date_str, username, display_name)
        diag_metrics = {
            "msg_db_count": len(msg_db_paths),
            "sender_map_size": len(sender_map),
            "my_rowid": my_rowid,
            "resolved_rows": 0,
            "decoded_nonempty": 0,
            "decoded_empty": 0,
            "self_matches": 0,
            "has_self_sql": False,
            "real_sender_missing": 0,
            "sender_map_missing": 0,
            "final_rows": 0,
        }
        diag_samples: list[dict[str, Any]] = []

        # Skip matchmaking/dating groups.
        if is_group and _is_matchmaking_group(display_name):
            logger.info("[daily-report] Skipping matchmaking group: %s (%s)", display_name, username)
            if diag:
                _diag_log_summary(
                    "sqlite",
                    "skipped_matchmaking",
                    date_str,
                    username,
                    display_name,
                    diag_metrics,
                )
            continue

        # Collect messages for this session from all message DBs.
        all_messages: list[str] = []
        has_my_messages = False
        max_msgs = 100
        max_chars = 16000

        for db_path in msg_db_paths:
            try:
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                try:
                    tbl = _resolve_msg_table_name(conn, username)
                    if not tbl:
                        continue

                    my_usernames = [account_dir.name]
                    if my_rowid is not None:
                        row = conn.execute(
                            "SELECT user_name FROM Name2Id WHERE rowid = ?",
                            (my_rowid,),
                        ).fetchone()
                        if row and row[0]:
                            my_usernames.append(str(row[0]))
                    my_usernames = list(dict.fromkeys([u for u in my_usernames if u]))
                    placeholders = ",".join(["?"] * len(my_usernames))
                    has_self_sql = f'''
                        SELECT 1
                        FROM "{tbl}" AS m
                        LEFT JOIN Name2Id AS n ON n.rowid = m.real_sender_id
                        WHERE m.create_time >= ? AND m.create_time < ?
                          AND n.user_name IN ({placeholders})
                        LIMIT 1
                    '''
                    has_self = conn.execute(
                        has_self_sql,
                        (start_ts, end_ts, *my_usernames),
                    ).fetchone() is not None
                    diag_metrics["has_self_sql"] = bool(has_self)

                    rows = conn.execute(
                        f'''SELECT m.local_type, m.create_time, m.sort_seq, m.local_id,
                                   m.real_sender_id, m.message_content, m.compress_content,
                                   n.user_name AS sender_username
                            FROM "{tbl}" AS m
                            LEFT JOIN Name2Id AS n ON n.rowid = m.real_sender_id
                            WHERE m.create_time >= ? AND m.create_time < ?
                            ORDER BY m.create_time ASC, m.sort_seq ASC, m.local_id ASC
                            LIMIT ?''',
                        (start_ts, end_ts, max_msgs),
                    ).fetchall()
                    diag_metrics["resolved_rows"] += len(rows)

                    for r in rows:
                        sender_uid = int(r["real_sender_id"]) if r["real_sender_id"] is not None else 0
                        sender_uname = str(r["sender_username"] or "") if "sender_username" in r.keys() else ""
                        if sender_uid <= 0:
                            diag_metrics["real_sender_missing"] += 1
                        if sender_uid and (not sender_uname):
                            diag_metrics["sender_map_missing"] += 1

                        # Decode message content.
                        raw = _decode_message_content(
                            r["compress_content"], r["message_content"]
                        )
                        text = (raw or "").strip()
                        if not text:
                            diag_metrics["decoded_empty"] += 1
                            continue
                        diag_metrics["decoded_nonempty"] += 1

                        alt_sender_prefix = ""
                        alt_sender_xml = ""
                        if is_group:
                            alt_sender_prefix, _ = _split_group_sender_prefix(text, sender_uname)
                            if text.startswith("<") or text.startswith('"<'):
                                alt_sender_xml = _extract_sender_from_group_xml(text)

                        is_sent = has_self and _sqlite_sender_matches_self(
                            account_name=account_dir.name,
                            my_rowid=my_rowid,
                            sender_uid=sender_uid,
                            sender_username=sender_uname,
                            alt_sender_prefix=alt_sender_prefix,
                            alt_sender_xml=alt_sender_xml,
                        )
                        if is_sent:
                            has_my_messages = True
                            diag_metrics["self_matches"] += 1

                        if diag and len(diag_samples) < 8:
                            diag_samples.append({
                                "sender_uid": sender_uid,
                                "sender_username": sender_uname,
                                "is_sent": is_sent,
                                "prefix_sender": alt_sender_prefix,
                                "xml_sender": alt_sender_xml,
                                "text_preview": text[:80],
                            })

                        # Build sender label.
                        if is_sent:
                            sender_label = "我"
                        elif is_group and sender_uname:
                            sender_label = _pick_display_name(contact_rows.get(sender_uname), sender_uname)
                        else:
                            sender_label = display_name

                        line = f"{sender_label}: {text}"
                        all_messages.append(line)

                        if len(all_messages) >= max_msgs:
                            break

                    if len(all_messages) >= max_msgs:
                        break

                finally:
                    conn.close()
            except Exception:
                logger.debug("[daily-report] Error querying %s for %s", db_path, username, exc_info=True)

        # Skip conversations where the user has no messages (没有回话的不生成日报).
        if not has_my_messages:
            logger.info(
                "[daily-report] Skipping conversation with no replies: %s (%s)",
                display_name, username,
            )
            if diag:
                _diag_log_summary(
                    "sqlite",
                    "skipped_no_self_messages",
                    date_str,
                    username,
                    display_name,
                    {**diag_metrics, "samples": diag_samples},
                )
            continue

        # Truncate total chars per conversation for LLM context.
        total = 0
        truncated: list[str] = []
        for line in all_messages:
            total += len(line) + 1
            if total > max_chars:
                break
            truncated.append(line)
        diag_metrics["final_rows"] = len(truncated)

        if truncated:
            conversations.append({
                "username": username,
                "display_name": display_name,
                "is_group": is_group,
                "messages": truncated,
            })
            if diag:
                _diag_log_summary(
                    "sqlite",
                    "included",
                    date_str,
                    username,
                    display_name,
                    {**diag_metrics, "samples": diag_samples},
                )
        elif diag:
            _diag_log_summary(
                "sqlite",
                "skipped_empty_after_decode",
                date_str,
                username,
                display_name,
                {**diag_metrics, "samples": diag_samples},
            )

    return conversations


# ── LLM analysis ──────────────────────────────────────────────────────────

_LLM_SYSTEM_PROMPT = """你是一个微信工作日报分析助手。你的任务是分析今日的聊天记录，识别出应该计入工作日报的对话。

核心原则：
- 只要是实际工作相关沟通，就必须计入日报
- 不要把“内部群”当作排除条件
- 不要只盯“客户咨询”，内部技术支援、项目实施、运维排障同样属于日报工作内容

必须计入日报（直接判定为 is_customer=true）的典型场景：
- 内部技术支援群、项目群、实施群、维护群、运维群、排障群
- 数据库相关沟通：SQL、索引、备份、恢复、迁移、升级、主备、容灾、巡检、性能优化
- 服务器/系统相关沟通：部署、配置、故障、修复、切换、上线、补丁、日志排查
- 医院/客户项目交付、培训、答疑、问题处理、远程协助
- 只要聊天内容明显是在处理工作事务，并且出现了实际问题分析、方案确认、操作安排、结果反馈，就应计入日报

不计入日报：
- 朋友闲聊、家庭群聊、兴趣群讨论、广告推销、纯娱乐闲聊等与工作无关内容

强规则：
- 如果群名或内容出现“技术支援、维护、实施、运维、排障、数据库、SQL、索引、备份、恢复、迁移、升级、主备、容灾、巡检、部署、配置、故障、服务器、培训、答疑、项目、医院、系统”等工作关键词，且聊天内容明显在处理工作事务，就必须标记为 is_customer=true
- 不要因为群名包含“内部”或因为参与者是同事，就判定为 false
- 对于内部技术支援群、数据库问题群、医院维护群、项目实施群，只要内容是实际工作处理，必须进入日报

对于每一段对话，请判断：
1. is_customer: 是否应计入工作日报（true/false）。这里表示“是否属于日报工作内容”，不只表示“客户”
2. customer_name: 工作对象名称（客户名、医院名、项目名、群名、系统名、人名等）。如果是内部技术支援群、项目群、维护群，可直接填写群名或项目名
3. summary: 用一句话概括核心结果，突出关键动作和产出（10-25字，仅对 should-report=true 的对话填写，其他留空）。要求直击重点，不罗列过程细节，让人一眼看明白今天做了什么

请严格按以下 JSON 格式返回结果，不要包含其他内容：
{"entries": [{"username": "...", "is_customer": true/false, "customer_name": "...", "summary": "..."}, ...]}

特别注意：
- 内部技术支援群、数据库问题群、医院维护群、项目实施群，只要当天讨论的是数据库、运维、排障、实施、系统处理等实际工作，就必须计入日报
- 所有群聊名称包含"相亲"的对话已经被过滤掉，你不需要再考虑"""


def _build_llm_user_message(conversations: list[dict]) -> str:
    parts: list[str] = []
    for conv in conversations:
        tag = "群聊" if conv["is_group"] else "私聊"
        header = f"[{tag}] {conv['display_name']} ({conv['username']})"
        parts.append(header)
        for msg in conv["messages"]:
            parts.append(f"  {msg}")
        parts.append("")  # blank line separator
    return "\n".join(parts)


def _try_parse_llm_response(text: str) -> list[dict]:
    """Best-effort extraction of JSON from LLM response."""
    # Try direct JSON parse.
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "entries" in data:
            return data["entries"]
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block.
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1).strip())
            if isinstance(data, dict) and "entries" in data:
                return data["entries"]
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    # Try finding JSON object/array in raw text.
    for delim in ("{", "["):
        idx = text.find(delim)
        if idx >= 0:
            try:
                data = json.loads(text[idx:])
                if isinstance(data, dict) and "entries" in data:
                    return data["entries"]
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                continue

    return []


async def _analyze_conversations_with_llm(
    conversations: list[dict],
    config: DailyReportConfig,
    *,
    date_str: str = "",
) -> tuple[list[dict], bool]:
    """Send conversations to LLM and return analyzed results.

    Returns (entries, was_analyzed) where was_analyzed indicates whether
    LLM analysis actually ran (vs. fallback when not configured / failed).
    """
    if not config.llm_base_url or not config.llm_api_key:
        logger.info("[daily-report] LLM not configured, skipping AI analysis")
        return _fallback_analysis(conversations), False

    headers = {
        "Authorization": f"Bearer {config.llm_api_key}",
        "Content-Type": "application/json",
    }

    user_msg = _build_llm_user_message(conversations)
    # Guard against overly long prompts.
    if len(user_msg) > 50000:
        user_msg = user_msg[:50000] + "\n...(truncated)"

    payload = {
        "model": config.llm_model,
        "messages": [
            {"role": "system", "content": _LLM_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": config.llm_max_tokens,
        "temperature": 0.1,
    }

    base_url = config.llm_base_url.rstrip("/")
    url = f"{base_url}/chat/completions"

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                body = resp.json()
                llm_text = body["choices"][0]["message"]["content"]
        except Exception:
            logger.exception("[daily-report] LLM call failed (attempt %d/2)", attempt + 1)
            if attempt == 0:
                await asyncio.sleep(5)
            continue

        entries = _try_parse_llm_response(llm_text)
        if entries:
            merged = _merge_llm_results(conversations, entries)
            if date_str:
                for item in merged:
                    if _diag_conversation_entry(date_str, item):
                        logger.info(
                            "[daily-report][diag][llm] stage=after_llm date=%s username=%s display_name=%s is_customer=%s customer_name=%s summary=%s",
                            date_str,
                            item.get("username") or "",
                            item.get("display_name") or "",
                            bool(item.get("is_customer")),
                            item.get("customer_name") or "",
                            item.get("summary") or "",
                        )
            return merged, True

        logger.warning("[daily-report] LLM returned unparseable response, falling back")
        return _fallback_analysis(conversations), False

    logger.error("[daily-report] LLM call failed after 2 attempts")
    return _fallback_analysis(conversations), False


def _merge_llm_results(
    conversations: list[dict],
    llm_entries: list[dict],
) -> list[dict]:
    """Merge LLM analysis results back with conversation metadata.

    The LLM may use display_name instead of the internal username as the key,
    so we look up by both fields.
    """
    llm_by_key: dict[str, dict] = {}
    for e in llm_entries:
        k = str(e.get("username") or "")
        if k:
            llm_by_key[k] = e

    results: list[dict] = []
    for conv in conversations:
        uname = conv["username"]
        dname = conv["display_name"]
        llm = llm_by_key.get(uname) or llm_by_key.get(dname) or {}
        results.append({
            "username": uname,
            "display_name": dname,
            "is_group": conv["is_group"],
            "is_customer": bool(llm.get("is_customer", False)),
            "customer_name": str(llm.get("customer_name", "") or ""),
            "summary": str(llm.get("summary", "") or ""),
        })
    return results


def _fallback_analysis(conversations: list[dict]) -> list[dict]:
    return [
        {
            "username": conv["username"],
            "display_name": conv["display_name"],
            "is_group": conv["is_group"],
            "is_customer": False,
            "customer_name": "",
            "summary": "",
        }
        for conv in conversations
    ]


def _merge_entries_by_customer(entries: list[dict], *, date_str: str = "") -> list[dict]:
    """Merge entries sharing the same non-empty customer_name into one.

    同一客户既在群聊又在私聊时合并为一条，摘要合并显示。
    """
    merged: dict[str, dict] = {}
    others: list[dict] = []
    for e in entries:
        cn = (e.get("customer_name") or "").strip()
        if not cn:
            others.append(e)
            if date_str and _diag_conversation_entry(date_str, e):
                logger.info(
                    "[daily-report][diag][merge] stage=pass_through date=%s username=%s display_name=%s is_customer=%s customer_name=%s summary=%s",
                    date_str,
                    e.get("username") or "",
                    e.get("display_name") or "",
                    bool(e.get("is_customer")),
                    e.get("customer_name") or "",
                    e.get("summary") or "",
                )
            continue
        if cn in merged:
            existing = merged[cn]
            # Merge summary
            existing_summaries = [s.strip() for s in (existing["summary"] or "").split("；") if s.strip()]
            current_summary = e.get("summary") or ""
            if current_summary.strip() and current_summary not in existing_summaries:
                existing_summaries.append(current_summary.strip())
            existing["summary"] = "；".join(existing_summaries)
            # Merge is_customer (True wins)
            if e.get("is_customer"):
                existing["is_customer"] = True
            # Merge display_name to show both sources
            existing_display = existing.get("display_name") or ""
            current_display = e.get("display_name") or ""
            if current_display and current_display not in existing_display:
                existing["display_name"] = f"{existing_display} / {current_display}"
            if date_str and (_diag_conversation_entry(date_str, e) or _diag_conversation_entry(date_str, existing)):
                logger.info(
                    "[daily-report][diag][merge] stage=merged date=%s source_username=%s source_display_name=%s target_display_name=%s customer_name=%s merged_summary=%s",
                    date_str,
                    e.get("username") or "",
                    e.get("display_name") or "",
                    existing.get("display_name") or "",
                    cn,
                    existing.get("summary") or "",
                )
        else:
            merged[cn] = dict(e)
            if date_str and _diag_conversation_entry(date_str, e):
                logger.info(
                    "[daily-report][diag][merge] stage=seed date=%s username=%s display_name=%s is_customer=%s customer_name=%s summary=%s",
                    date_str,
                    e.get("username") or "",
                    e.get("display_name") or "",
                    bool(e.get("is_customer")),
                    e.get("customer_name") or "",
                    e.get("summary") or "",
                )
    return list(merged.values()) + others


# ── orchestrator ──────────────────────────────────────────────────────────

async def generate_daily_report(
    date_str: str | None = None,
    account: str | None = None,
) -> dict:
    """Generate a daily report. Returns the report dict."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Guard against concurrent generation for the same date.
    if date_str in _generating_lock:
        return {"date": date_str, "status": "in_progress", "entries": []}
    _generating_lock.add(date_str)
    try:
        config = _read_daily_report_config()
        if account is None:
            account = config.account

        # Resolve account - this will raise HTTPException if not found.
        account_dir = _resolve_account_dir(account)
        account_name = account_dir.name

        logger.info("[daily-report] Generating report for %s (account: %s)", date_str, account_name)

        # Step 1: collect messages (blocking DB I/O -> thread).
        conversations = await asyncio.to_thread(
            _collect_account_day_messages, account_dir, date_str
        )
        logger.info(
            "[daily-report] Collected %d conversations with messages",
            len(conversations),
        )

        # Step 2: LLM analysis.
        analyzed, llm_analyzed = await _analyze_conversations_with_llm(
            conversations,
            config,
            date_str=date_str,
        )

        # Step 2b: merge entries for the same customer (同一客户既在群聊又在私聊时合并为一条).
        analyzed = _merge_entries_by_customer(analyzed, date_str=date_str)

        # Step 2c: preserve manually added entries (手工登记) from the old report
        # so they are not overwritten on regeneration. We identify them by the
        # _is_manual flag (set by POST /api/reports/{date}/entries) or, for
        # backward compatibility with entries saved before the flag existed, by
        # empty username.
        old_report = _load_report(date_str)
        if old_report:
            custom = [
                e for e in old_report.get("entries", [])
                if e.get("_is_manual") or not e.get("username")
            ]
            if custom:
                analyzed.extend(custom)
                logger.info(
                    "[daily-report] Preserved %d custom entries for %s", len(custom), date_str
                )

        # Step 3: build and save report.
        report = {
            "date": date_str,
            "generated_at": int(time.time()),
            "account": account_name,
            "llm_model": config.llm_model if config.llm_base_url and config.llm_api_key else None,
            "llm_analyzed": llm_analyzed,
            "llm_configured": bool(config.llm_base_url and config.llm_api_key),
            "entries": analyzed,
        }
        _save_report(date_str, report)
        logger.info("[daily-report] Report saved for %s", date_str)

        return report
    finally:
        _generating_lock.discard(date_str)


# ── scheduler ─────────────────────────────────────────────────────────────

class DailyReportScheduler:
    """Background asyncio task that generates daily reports at the configured time."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("[daily-report] Scheduler started")

    def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            self._task = None
        logger.info("[daily-report] Scheduler stopped")

    async def _run_loop(self) -> None:
        config = _read_daily_report_config()
        if not config.enabled:
            logger.info("[daily-report] Daily report is disabled via config")
            return

        while not self._stop.is_set():
            now = datetime.now()
            try:
                target = datetime.strptime(config.schedule_time, "%H:%M").time()
            except ValueError:
                logger.error("[daily-report] Invalid schedule_time: %s", config.schedule_time)
                return

            scheduled = datetime(now.year, now.month, now.day, target.hour, target.minute)
            if scheduled <= now:
                scheduled += timedelta(days=1)

            wait_seconds = (scheduled - now).total_seconds()
            logger.info(
                "[daily-report] Next report scheduled at %s (in %d seconds)",
                scheduled.strftime("%Y-%m-%d %H:%M"), int(wait_seconds),
            )

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=wait_seconds)
                break  # stop was requested
            except asyncio.TimeoutError:
                pass  # time to generate

            date_str = datetime.now().strftime("%Y-%m-%d")
            try:
                await generate_daily_report(date_str=date_str)
            except Exception:
                logger.exception("[daily-report] Failed to generate report for %s", date_str)

            # Wait 23 hours before re-checking (avoids drift).
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=23 * 3600)
                break
            except asyncio.TimeoutError:
                pass


# Module-level singleton (same pattern as CHAT_REALTIME_AUTOSYNC).
DAILY_REPORT_SCHEDULER = DailyReportScheduler()
