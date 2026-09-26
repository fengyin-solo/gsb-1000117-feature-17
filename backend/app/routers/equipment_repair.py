"""仪器维修接口：维护维修记录，覆盖派工维修、确认修复、标记报废等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.equipment_repair import (
    FILTERABLE_FIELDS,
    SORTABLE_FIELDS,
    STATUS_ORDER,
    EquipmentRepairService,
)

router = APIRouter(prefix="/api/equipment_repair", tags=["仪器维修"])

service = EquipmentRepairService()

LIST_FIELDS = ["维修编号", "仪器编号", "故障描述", "报修人", "报修日期", "维修单位", "修复日期", "维修状态"]
STATUSES = STATUS_ORDER


@router.get("", response_model=PageResult[dict])
def list_entries(
    维修编号: str | None = Query(default=None, description="按维修编号模糊检索"),
    仪器编号: str | None = Query(default=None, description="按仪器编号模糊检索"),
    故障描述: str | None = Query(default=None, description="按故障描述模糊检索"),
    报修人: str | None = Query(default=None, description="按报修人模糊检索"),
    status: str | None = Query(default=None, description="已报修、维修中、已修复、无法修复 四选一"),
    sort_by: str = Query(default="维修编号", description="排序列"),
    order: str = Query(default="asc", description="asc 或 desc"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按维修编号、仪器编号、故障描述、报修人与状态过滤列表；空结果返回空页，不报错。

    列表数据与数量指标在同一响应内返回，前端切换条件时两者一起更新，不会短暂错位。
    """
    if page < 1:
        raise HTTPException(status_code=400, detail="页码需从 1 开始")
    if not 1 <= size <= 200:
        raise HTTPException(status_code=400, detail="每页条数需在 1 到 200 之间，请缩小分页范围")
    if status is not None and status not in STATUSES:
        raise HTTPException(status_code=400, detail=f"维修状态仅支持：{'、'.join(STATUSES)}")
    if sort_by not in SORTABLE_FIELDS:
        raise HTTPException(status_code=400, detail=f"仅支持按 {'、'.join(SORTABLE_FIELDS)} 排序")
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="排序方向仅支持 asc 或 desc")

    filters = {
        field: value.strip()
        for field, value in zip(FILTERABLE_FIELDS, (维修编号, 仪器编号, 故障描述, 报修人))
        if value and value.strip()
    }
    items, total = service.list_entries(
        filters=filters,
        status=status,
        sort_by=sort_by,
        order=order,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size, stats=service.summary())


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出仪器维修清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "equipment_repair", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条维修记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"维修记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条维修记录，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="维修记录已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条维修记录执行派工维修、确认修复、标记报废；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
