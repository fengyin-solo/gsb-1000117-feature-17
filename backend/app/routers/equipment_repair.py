"""仪器维修接口：维护维修记录，覆盖派工维修、确认修复、标记报废等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.equipment_repair import SORTABLE_FIELDS, EquipmentRepairService

router = APIRouter(prefix="/api/equipment_repair", tags=["仪器维修"])

service = EquipmentRepairService()

LIST_FIELDS = ["维修编号", "仪器编号", "故障描述", "报修人", "报修日期", "维修单位", "修复日期", "维修状态"]
STATUSES = ["已报修", "维修中", "已修复", "无法修复"]


class EquipmentRepairPage(PageResult[dict]):
    """仪器维修列表页：分页数据与统计卡片同帧返回，前端不会出现列表新、数量旧的错位。"""

    stats: list[dict[str, Any]] = Field(default_factory=list)


@router.get("", response_model=EquipmentRepairPage)
def list_entries(
    keyword: str | None = Query(default=None, description="按维修编号检索"),
    repair_no: str | None = Query(default=None, description="按维修编号筛选"),
    instrument_no: str | None = Query(default=None, description="按仪器编号筛选"),
    fault: str | None = Query(default=None, description="按故障描述筛选"),
    reporter: str | None = Query(default=None, description="按报修人筛选"),
    status: str | None = Query(default=None, description="已报修、维修中、已修复、无法修复"),
    sort: str | None = Query(default=None, description="排序字段：维修编号、仪器编号、故障描述、报修人"),
    order: str = Query(default="asc", description="排序方向：asc 升序、desc 降序"),
    page: int = 1,
    size: int = 20,
) -> EquipmentRepairPage:
    """按条件查询仪器维修列表；条件冲突或越界时给出明确说明，不静默忽略。"""
    if keyword and repair_no:
        raise HTTPException(status_code=400, detail="keyword 与 repair_no 都是维修编号条件，二者互斥，请只保留一个")
    if sort is not None and sort not in SORTABLE_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"排序字段「{sort}」不支持，可选：{'、'.join(SORTABLE_FIELDS)}",
        )
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="排序方向只支持 asc 或 desc")
    if page < 1:
        raise HTTPException(status_code=400, detail="页码从 1 开始")
    if size < 1 or size > 200:
        raise HTTPException(status_code=400, detail="每页 1-200 条，请调整分页范围")
    filters = {"维修编号": repair_no, "仪器编号": instrument_no, "故障描述": fault, "报修人": reporter}
    items, total, page = service.list_entries(
        keyword=keyword,
        filters=filters,
        status=status,
        sort=sort,
        order=order,
        page=page,
        size=size,
    )
    return EquipmentRepairPage(items=items, total=total, page=page, size=size, stats=service.stats())


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出仪器维修清单：返回当前过滤条件下的全量数据。"""
    items, total, _ = service.list_entries(page=1, size=10000)
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
