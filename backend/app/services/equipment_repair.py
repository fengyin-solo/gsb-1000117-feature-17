"""仪器维修业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "equipment_repair"
REQUIRED_FIELDS = ["维修编号", "仪器编号", "故障描述"]
FILTER_FIELDS = ["维修编号", "仪器编号", "故障描述", "报修人"]
SORTABLE_FIELDS = ["维修编号", "仪器编号", "故障描述", "报修人"]
STATUS_ORDER = ["已报修", "维修中", "已修复", "无法修复"]
ACTION_RULES = {"派工维修": "维修中", "确认修复": "已修复", "标记报废": "无法修复"}
NEGATIVE_ACTIONS = []


class EquipmentRepairService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        filters: dict[str, str | None] | None = None,
        status: str | None = None,
        sort: str | None = None,
        order: str = "asc",
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, int]:
        """筛选、排序、分页一次算完，返回（当前页数据, 总条数, 实际页码）。

        页码超出范围时收拢到最后一页，调用方拿实际页码回写给前端，
        避免筛选后旧页码对着空屏。
        """
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("维修编号", ""))]
        for field, value in (filters or {}).items():
            if field in FILTER_FIELDS and value:
                rows = [row for row in rows if value in str(row.get(field, ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if sort:
            rows = sorted(
                rows,
                key=lambda row: (str(row.get(sort) or ""), int(row.get("id", 0))),
                reverse=order == "desc",
            )
        total = len(rows)
        max_page = max(1, -(-total // size))
        page = min(max(page, 1), max_page)
        start = (page - 1) * size
        return rows[start:start + size], total, page

    def stats(self) -> list[dict[str, Any]]:
        """统计卡片与列表同一次响应给出，保证数量指标不和列表错位。"""
        rows = store.rows(MODULE)
        month = date.today().strftime("%Y-%m")
        return [
            {"label": "待维修仪器", "value": sum(1 for row in rows if row.get("status") == "已报修")},
            {"label": "维修中仪器", "value": sum(1 for row in rows if row.get("status") == "维修中")},
            {
                "label": "本月修复",
                "value": sum(
                    1
                    for row in rows
                    if row.get("status") == "已修复" and str(row.get("修复日期", "")).startswith(month)
                ),
            },
        ]

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"维修记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于仪器维修可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"维修记录已{action}"
