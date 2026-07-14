from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from ..daily_report_service import (
    _load_report,
    _list_report_dates,
    _save_report,
    generate_daily_report,
)
from ..path_fix import PathFixRoute

router = APIRouter(route_class=PathFixRoute)


class ReportEntry(BaseModel):
    username: str = ""
    display_name: str = ""
    is_group: bool = False
    is_customer: bool = False
    customer_name: str = ""
    summary: str = ""


class UpdateReportRequest(BaseModel):
    entries: list[ReportEntry]


@router.get("/api/reports", summary="获取日报列表")
async def list_reports():
    """返回所有已生成的日报日期列表。"""
    dates = _list_report_dates()
    return {"dates": dates}


@router.get("/api/reports/today", summary="获取今日日报")
async def get_today_report(
    generate_if_missing: bool = Query(
        False, description="如果今日日报不存在，是否立即生成"
    ),
    account: Optional[str] = Query(
        None, description="解密后的账号目录名。默认取第一个可用账号。"
    ),
):
    """获取今天的日报。如果不存在且 generate_if_missing=true，则实时生成。"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    report = _load_report(date_str)
    if report is not None:
        return {"date": date_str, "report": report}

    if generate_if_missing:
        report = await generate_daily_report(date_str=date_str, account=account)
        return {"date": date_str, "report": report}

    return {"date": date_str, "report": None, "message": "今日日报尚未生成。设置 generate_if_missing=true 可立即生成。"}


_batch_task_ref: set[asyncio.Task] = set()


@router.post("/api/reports/generate-batch", summary="批量生成日报")
async def trigger_batch_generation(
    account: Optional[str] = Query(
        None, description="解密后的账号目录名。默认取第一个可用账号。"
    ),
    start_date: str = Query(
        ..., description="开始日期，格式 YYYY-MM-DD",
    ),
    end_date: str = Query(
        ..., description="结束日期，格式 YYYY-MM-DD",
    ),
):
    """批量生成指定日期范围内的日报。每个日期在后台依次生成。"""
    try:
        sd = datetime.strptime(start_date, "%Y-%m-%d")
        ed = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的日期格式，应为 YYYY-MM-DD")

    if sd > ed:
        raise HTTPException(status_code=400, detail="start_date 不能晚于 end_date")

    today = datetime.now().strftime("%Y-%m-%d")
    if end_date > today:
        raise HTTPException(status_code=400, detail="不能生成未来的日报")

    from ..daily_report_service import _generating_lock

    dates: list[str] = []
    current = sd
    while current <= ed:
        ds = current.strftime("%Y-%m-%d")
        if ds not in _generating_lock:
            _generating_lock.add(ds)
            dates.append(ds)
        current += timedelta(days=1)

    if not dates:
        return {"status": "done", "dates": [], "message": "所选日期均已生成或正在生成中"}

    task = asyncio.ensure_future(_run_batch_generate(dates, account))
    _batch_task_ref.add(task)
    task.add_done_callback(_batch_task_ref.discard)
    return {
        "status": "generating",
        "dates": dates,
        "message": f"已提交 {len(dates)} 天的日报生成任务，请在生成完成后查看",
    }


async def _run_batch_generate(dates: list[str], account: Optional[str]) -> None:
    """Run batch generation sequentially."""
    from ..daily_report_service import _generating_lock
    from ..logging_config import get_logger
    logger = get_logger(__name__)

    for ds in dates:
        # Remove from lock before calling generate_daily_report, because
        # generate_daily_report itself uses _generating_lock to prevent
        # concurrent generation for the same date. If we leave the date
        # in the lock, generate_daily_report will see it and return early
        # without doing any actual work.
        _generating_lock.discard(ds)
        try:
            await generate_daily_report(date_str=ds, account=account)
            logger.info("[daily-report] Batch generated %s", ds)
        except Exception:
            logger.exception("[daily-report] Batch generation failed for %s", ds)
        finally:
            _generating_lock.discard(ds)


@router.get("/api/reports/{date}", summary="获取指定日期的日报")
async def get_report_by_date(date: str):
    """获取指定日期的日报。

    Args:
        date: 日期，格式 YYYY-MM-DD。
    """
    # Basic format validation.
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的日期格式: {date}，应为 YYYY-MM-DD")

    report = _load_report(date)
    if report is None:
        raise HTTPException(status_code=404, detail=f"未找到 {date} 的日报")
    return {"date": date, "report": report}


@router.post("/api/reports/generate", summary="手动触发日报生成")
async def trigger_report_generation(
    background_tasks: BackgroundTasks,
    account: Optional[str] = Query(
        None, description="解密后的账号目录名。默认取第一个可用账号。"
    ),
    date: Optional[str] = Query(
        None, description="日期，格式 YYYY-MM-DD。默认今日。",
    ),
):
    """手动触发日报生成。生成过程在后台执行，接口立即返回。"""
    date_str = date or datetime.now().strftime("%Y-%m-%d")

    if date:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的日期格式: {date_str}，应为 YYYY-MM-DD")

    from ..daily_report_service import _generating_lock

    if date_str in _generating_lock:
        return {"status": "in_progress", "date": date_str, "message": "该日日报正在生成中"}

    background_tasks.add_task(_run_generate_in_background, date_str, account)
    return {"status": "generating", "date": date_str, "message": "日报生成任务已提交，请稍后查看"}


async def _run_generate_in_background(date_str: str, account: Optional[str]) -> None:
    """Run report generation in the background task pool."""
    try:
        await generate_daily_report(date_str=date_str, account=account)
    except Exception:
        from ..logging_config import get_logger
        logger = get_logger(__name__)
        logger.exception("[daily-report] Background generation failed for %s", date_str)


@router.put("/api/reports/{date}", summary="更新日报条目")
async def update_report(date: str, body: UpdateReportRequest) -> dict:
    """更新指定日期的日报条目（替换全部 entries）。"""
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的日期格式: {date}，应为 YYYY-MM-DD")

    report = _load_report(date)
    if report is None:
        raise HTTPException(status_code=404, detail=f"未找到 {date} 的日报")

    report["entries"] = [e.model_dump() for e in body.entries]
    _save_report(date, report)
    return {"success": True, "date": date, "report": report}


@router.post("/api/reports/{date}/entries", summary="添加自定义条目")
async def add_custom_entry(date: str, body: ReportEntry) -> dict:
    """向指定日期的日报添加一条自定义条目（不会出现在微信聊天中）。"""
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的日期格式: {date}，应为 YYYY-MM-DD")

    report = _load_report(date)
    if report is None:
        report = {
            "date": date,
            "generated_at": int(__import__("time").time()),
            "account": "",
            "llm_model": None,
            "entries": [],
        }

    entry = body.model_dump()
    entry["_is_manual"] = True
    report["entries"].append(entry)
    _save_report(date, report)
    return {"success": True, "entry": entry}
