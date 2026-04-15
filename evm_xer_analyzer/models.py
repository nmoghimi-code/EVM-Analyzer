from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ProjectInfo:
    project_id: str
    short_name: str
    data_date: datetime
    default_calendar_id: str | None
    default_day_hours: float


@dataclass(slots=True)
class WBSNode:
    wbs_id: str
    parent_wbs_id: str | None
    short_name: str
    name: str


@dataclass(slots=True)
class TaskRecord:
    task_id: str
    wbs_id: str
    task_code: str
    task_name: str
    status_code: str
    total_duration_hours: float
    remaining_duration_hours: float
    physical_percent_complete: float
    act_start: datetime | None
    act_end: datetime | None
    target_start: datetime | None
    target_end: datetime | None
    early_start: datetime | None
    early_end: datetime | None


@dataclass(slots=True)
class ScheduleData:
    project: ProjectInfo
    wbs_by_id: dict[str, WBSNode]
    children_by_parent: dict[str | None, list[str]]
    tasks: list[TaskRecord]


@dataclass(slots=True)
class WBSMatch:
    search_term: str
    wbs_id: str
    short_name: str
    name: str
    path: str


@dataclass(slots=True)
class AnalysisRow:
    search_term: str
    matched_wbs: str
    matched_wbs_name: str
    matched_wbs_path: str
    baseline_total_days: float
    baseline_planned_days: float
    baseline_planned_percent: float
    current_total_days: float
    current_actual_days: float
    current_actual_percent: float
    spi: float | None
    current_forecast_finish: datetime | None
    current_remaining_span_days: float
    revised_remaining_span_days: float | None
    revised_finish_date: datetime | None
    variance_percent_points: float
    baseline_task_count: int
    current_task_count: int
