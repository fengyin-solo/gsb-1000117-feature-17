"""仪器维修业务规则：状态流转、字段校验、筛选排序与指标统计都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "equipment_repair"
REQUIRED_FIELDS = ["维修编号", "仪器编号", "故障描述", "报修人"]
STATUS_ORDER = ["已报修", "维修中", "已修复", "无法修复"]
ACTION_RULES = {"派工维修": "维修中", "确认修复": "已修复", "标记报废": "无法修复"}
NEGATIVE_ACTIONS = ["标记报废"]

# 列表允许按这四列排序，与页面表头一致；其余列不接受排序入参。
SORTABLE_FIELDS = ["维修编号", "仪器编号", "故障描述", "报修人"]
# 每一列支持的模糊筛选字段。
FILTERABLE_FIELDS = SORTABLE_FIELDS


class EquipmentRepairService:
    def list_entries(
        self,
        *,
        filters: dict[str, str] | None = None,
        status: str | None = None,
        sort_by: str = "维修编号",
        order: str = "asc",
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        for field, keyword in (filters or {}).items():
            if field in FILTERABLE_FIELDS and keyword:
                rows = [row for row in rows if keyword.lower() in str(row.get(field, "")).lower()]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)

        reverse = order == "desc"
        rows = sorted(rows, key=lambda row: str(row.get(sort_by, "")), reverse=reverse)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def summary(self) -> dict[str, int]:
        """列表顶部指标：始终统计全量数据，与具体筛选条件解耦，避免数量与列表错位。"""
        rows = store.rows(MODULE)
        current_month = date.today().strftime("%Y-%m")
        return {
            "待维修仪器": sum(1 for row in rows if row.get("status") == "已报修"),
            "维修中仪器": sum(1 for row in rows if row.get("status") == "维修中"),
            "本月修复": sum(
                1
                for row in rows
                if row.get("status") == "已修复" and str(row.get("修复日期", "")).startswith(current_month)
            ),
            "已修复": sum(1 for row in rows if row.get("status") == "已修复"),
            "无法修复": sum(1 for row in rows if row.get("status") == "无法修复"),
        }

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["报修日期"] = values.get("报修日期") or date.today().isoformat()
        entry["维修单位"] = values.get("维修单位")
        entry["修复日期"] = None
        entry["status"] = STATUS_ORDER[0]
        entry["维修状态"] = entry["status"]
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
        # 列表的“维修状态”列与内部 status 保持同源，避免动作后两列显示不一致。
        entry["维修状态"] = target
        if action == "确认修复":
            entry["修复日期"] = date.today().isoformat()
        entry["pending"] = target == "已报修" or target == "维修中"
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"维修记录已{action}"
