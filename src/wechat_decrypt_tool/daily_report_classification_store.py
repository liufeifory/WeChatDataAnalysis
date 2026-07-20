from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from .app_paths import get_output_dir


CLASSIFICATION_FILENAME = "daily_report_classification.json"
_VALID_CATEGORIES = {"customer", "internal", "ignore"}


def _classification_path() -> Path:
    return get_output_dir() / CLASSIFICATION_FILENAME


def _default_config() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": 0,
        "customers": [],
        "rules": [],
    }


def _load_classification_config() -> dict[str, Any]:
    path = _classification_path()
    if not path.exists():
        return _default_config()
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return _default_config()
    if not isinstance(data, dict):
        return _default_config()
    cfg = _default_config()
    cfg.update(data)
    if not isinstance(cfg.get("customers"), list):
        cfg["customers"] = []
    if not isinstance(cfg.get("rules"), list):
        cfg["rules"] = []
    return cfg


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _validate_customer(item: dict[str, Any]) -> dict[str, str]:
    cid = str(item.get("id") or "").strip()
    name = str(item.get("name") or "").strip()
    if not cid:
        cid = f"cust_{uuid.uuid4().hex[:12]}"
    if not name:
        raise ValueError("客户名称不能为空")
    return {"id": cid, "name": name}


def _validate_rule(item: dict[str, Any], customers: list[dict[str, str]]) -> dict[str, Any]:
    rid = str(item.get("id") or "").strip() or f"rule_{uuid.uuid4().hex[:12]}"
    match_type = str(item.get("match_type") or "username").strip() or "username"
    match_value = str(item.get("match_value") or item.get("username") or "").strip()
    display_name = str(item.get("display_name") or "").strip()
    category = str(item.get("category") or "").strip()
    enabled = bool(item.get("enabled", True))
    note = str(item.get("note") or "").strip()
    is_group = bool(item.get("is_group", False))
    customer_id = str(item.get("customer_id") or "").strip()
    customer_name = str(item.get("customer_name") or "").strip()

    if match_type != "username":
        raise ValueError("仅支持按 username 匹配")
    if not match_value:
        raise ValueError("匹配值不能为空")
    if category not in _VALID_CATEGORIES:
        raise ValueError("分类无效")

    customer_map = {str(c.get("id") or ""): str(c.get("name") or "") for c in customers}
    if category == "customer":
        if not customer_id:
            raise ValueError("客户类规则必须绑定客户")
        if customer_id not in customer_map:
            raise ValueError("绑定的客户不存在")
        customer_name = customer_map[customer_id]
    else:
        customer_id = ""
        customer_name = ""

    return {
        "id": rid,
        "match_type": match_type,
        "match_value": match_value,
        "display_name": display_name,
        "is_group": is_group,
        "category": category,
        "enabled": enabled,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "note": note,
    }


def get_daily_report_classification() -> dict[str, Any]:
    return _load_classification_config()


def save_daily_report_customers(customers: list[dict[str, Any]]) -> dict[str, Any]:
    cfg = _load_classification_config()
    normalized = [_validate_customer(item if isinstance(item, dict) else {}) for item in customers]
    cfg["customers"] = normalized

    existing_rules = cfg.get("rules", [])
    normalized_rules = []
    seen = set()
    for item in existing_rules:
        rule = _validate_rule(item if isinstance(item, dict) else {}, normalized)
        key = (rule["match_type"], rule["match_value"])
        if key in seen:
            raise ValueError("存在重复规则")
        seen.add(key)
        normalized_rules.append(rule)
    cfg["rules"] = normalized_rules
    cfg["updated_at"] = int(time.time())
    _atomic_write_json(_classification_path(), cfg)
    return cfg


def create_daily_report_rule(payload: dict[str, Any]) -> dict[str, Any]:
    cfg = _load_classification_config()
    customers = cfg.get("customers", [])
    rules = cfg.get("rules", [])
    rule = _validate_rule(payload if isinstance(payload, dict) else {}, customers)
    key = (rule["match_type"], rule["match_value"])
    for item in rules:
        if not isinstance(item, dict):
            continue
        if (str(item.get("match_type") or "username"), str(item.get("match_value") or "")) == key:
            raise ValueError("该会话已存在规则")
    rules.append(rule)
    cfg["rules"] = rules
    cfg["updated_at"] = int(time.time())
    _atomic_write_json(_classification_path(), cfg)
    return rule


def update_daily_report_rule(rule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    cfg = _load_classification_config()
    customers = cfg.get("customers", [])
    rules = cfg.get("rules", [])
    target_idx = -1
    for idx, item in enumerate(rules):
        if isinstance(item, dict) and str(item.get("id") or "") == str(rule_id or ""):
            target_idx = idx
            break
    if target_idx < 0:
        raise KeyError("rule_not_found")

    merged = dict(rules[target_idx])
    merged.update(payload if isinstance(payload, dict) else {})
    merged["id"] = str(rule_id or "")
    rule = _validate_rule(merged, customers)
    key = (rule["match_type"], rule["match_value"])
    for idx, item in enumerate(rules):
        if idx == target_idx or not isinstance(item, dict):
            continue
        other_key = (str(item.get("match_type") or "username"), str(item.get("match_value") or ""))
        if other_key == key:
            raise ValueError("该会话已存在规则")
    rules[target_idx] = rule
    cfg["rules"] = rules
    cfg["updated_at"] = int(time.time())
    _atomic_write_json(_classification_path(), cfg)
    return rule


def delete_daily_report_rule(rule_id: str) -> dict[str, Any]:
    cfg = _load_classification_config()
    rules = cfg.get("rules", [])
    new_rules = [item for item in rules if not (isinstance(item, dict) and str(item.get("id") or "") == str(rule_id or ""))]
    if len(new_rules) == len(rules):
        raise KeyError("rule_not_found")
    cfg["rules"] = new_rules
    cfg["updated_at"] = int(time.time())
    _atomic_write_json(_classification_path(), cfg)
    return cfg


def list_daily_report_rule_candidates(limit: int = 300) -> list[dict[str, Any]]:
    from .chat_helpers import _list_decrypted_accounts, _load_contact_rows, _pick_display_name, _resolve_account_dir

    accounts = _list_decrypted_accounts()
    if not accounts:
        return []
    account_dir = _resolve_account_dir(accounts[0])
    contact_db_path = account_dir / "contact.db"
    session_db_path = account_dir / "session.db"
    if not session_db_path.exists():
        return []

    import sqlite3

    conn = sqlite3.connect(str(session_db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT username FROM SessionTable ORDER BY sort_timestamp DESC LIMIT ?",
            (max(1, int(limit or 300)),),
        ).fetchall()
    finally:
        conn.close()

    usernames = [str(row["username"] or "").strip() for row in rows if row["username"]]
    usernames = [u for u in usernames if u]
    contact_rows = _load_contact_rows(contact_db_path, usernames)
    out = []
    for username in usernames:
        out.append({
            "username": username,
            "display_name": _pick_display_name(contact_rows.get(username), username),
            "is_group": bool(username.endswith("@chatroom")),
        })
    return out


def find_daily_report_rule(username: str) -> dict[str, Any] | None:
    u = str(username or "").strip()
    if not u:
        return None
    cfg = _load_classification_config()
    for item in cfg.get("rules", []):
        if not isinstance(item, dict):
            continue
        if not bool(item.get("enabled", True)):
            continue
        if str(item.get("match_type") or "username") != "username":
            continue
        if str(item.get("match_value") or "") == u:
            return item
    return None
