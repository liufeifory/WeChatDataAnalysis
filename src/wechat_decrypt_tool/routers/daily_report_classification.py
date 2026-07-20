from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..daily_report_classification_store import (
    create_daily_report_rule,
    delete_daily_report_rule,
    get_daily_report_classification,
    list_daily_report_rule_candidates,
    save_daily_report_customers,
    update_daily_report_rule,
)
from ..path_fix import PathFixRoute

router = APIRouter(route_class=PathFixRoute)


class CustomerItem(BaseModel):
    id: str = ""
    name: str = ""


class ClassificationRuleItem(BaseModel):
    id: str = ""
    match_type: str = "username"
    match_value: str = ""
    display_name: str = ""
    is_group: bool = False
    category: str = ""
    enabled: bool = True
    customer_id: str = ""
    customer_name: str = ""
    note: str = ""


class CustomersRequest(BaseModel):
    customers: list[CustomerItem]


class RuleRequest(BaseModel):
    rule: ClassificationRuleItem


@router.get("/api/daily-report-classification", summary="获取日报归类配置")
async def get_classification_config() -> dict[str, Any]:
    return get_daily_report_classification()


@router.put("/api/daily-report-classification/customers", summary="更新日报客户列表")
async def put_classification_customers(body: CustomersRequest) -> dict[str, Any]:
    try:
        return save_daily_report_customers([item.model_dump() for item in body.customers])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/daily-report-classification/rules", summary="新增日报归类规则")
async def post_classification_rule(body: RuleRequest) -> dict[str, Any]:
    try:
        rule = create_daily_report_rule(body.rule.model_dump())
        return {"success": True, "rule": rule}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/api/daily-report-classification/rules/{rule_id}", summary="更新日报归类规则")
async def put_classification_rule(rule_id: str, body: RuleRequest) -> dict[str, Any]:
    try:
        rule = update_daily_report_rule(rule_id, body.rule.model_dump())
        return {"success": True, "rule": rule}
    except KeyError:
        raise HTTPException(status_code=404, detail="规则不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/api/daily-report-classification/rules/{rule_id}", summary="删除日报归类规则")
async def delete_classification_rule(rule_id: str) -> dict[str, Any]:
    try:
        delete_daily_report_rule(rule_id)
        return {"success": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="规则不存在")


@router.get("/api/daily-report-classification/candidates", summary="获取日报归类候选会话")
async def get_classification_candidates(limit: int = 300) -> dict[str, Any]:
    return {"items": list_daily_report_rule_candidates(limit=limit)}
