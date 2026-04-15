from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .models import ProjectInfo, ScheduleData, TaskRecord, WBSNode

DATETIME_FORMAT = "%Y-%m-%d %H:%M"
EMPTY_DATE_VALUES = {"", "1899-12-30 00:00"}


@dataclass(slots=True)
class ParsedXER:
    tables: dict[str, list[dict[str, str]]]


def parse_xer_file(path: str | Path) -> ScheduleData:
    parsed = _parse_xer_tables(Path(path))
    project = _parse_project(parsed.tables)
    wbs_by_id, children_by_parent = _parse_wbs(parsed.tables)
    tasks = _parse_tasks(parsed.tables)
    return ScheduleData(
        project=project,
        wbs_by_id=wbs_by_id,
        children_by_parent=children_by_parent,
        tasks=tasks,
    )


def _parse_xer_tables(path: Path) -> ParsedXER:
    current_table: str | None = None
    current_fields: list[str] | None = None
    tables: dict[str, list[dict[str, str]]] = defaultdict(list)

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw_line:
            continue
        parts = raw_line.rstrip("\r").split("\t")
        record_type = parts[0]

        if record_type == "%T":
            current_table = parts[1]
            current_fields = None
            continue

        if current_table is None:
            continue

        if record_type == "%F":
            current_fields = parts[1:]
            continue

        if record_type != "%R" or current_fields is None:
            continue

        values = parts[1:]
        if len(values) < len(current_fields):
            values.extend([""] * (len(current_fields) - len(values)))
        if len(values) > len(current_fields):
            values = values[: len(current_fields)]
        tables[current_table].append(dict(zip(current_fields, values)))

    return ParsedXER(tables=dict(tables))


def _parse_project(tables: dict[str, list[dict[str, str]]]) -> ProjectInfo:
    project_records = tables.get("PROJECT", [])
    if not project_records:
        raise ValueError("The XER file does not contain a PROJECT table.")

    project_record = project_records[0]
    default_calendar_id = _clean_text(project_record.get("clndr_id"))
    data_date = _parse_datetime(
        project_record.get("last_recalc_date")
        or project_record.get("apply_actuals_date")
        or project_record.get("last_schedule_date")
    )
    if data_date is None:
        raise ValueError("Could not determine a valid project data date from the XER file.")

    default_day_hours = _parse_calendar_day_hours(tables, default_calendar_id) or 8.0

    return ProjectInfo(
        project_id=_clean_text(project_record.get("proj_id")),
        short_name=_clean_text(project_record.get("proj_short_name")),
        data_date=data_date,
        default_calendar_id=default_calendar_id,
        default_day_hours=default_day_hours,
    )


def _parse_calendar_day_hours(
    tables: dict[str, list[dict[str, str]]],
    default_calendar_id: str | None,
) -> float | None:
    if not default_calendar_id:
        return None

    for calendar in tables.get("CALENDAR", []):
        if _clean_text(calendar.get("clndr_id")) != default_calendar_id:
            continue
        day_hr_cnt = _parse_float(calendar.get("day_hr_cnt"))
        if day_hr_cnt and day_hr_cnt > 0:
            return day_hr_cnt
    return None


def _parse_wbs(
    tables: dict[str, list[dict[str, str]]],
) -> tuple[dict[str, WBSNode], dict[str | None, list[str]]]:
    wbs_by_id: dict[str, WBSNode] = {}
    children_by_parent: dict[str | None, list[str]] = defaultdict(list)

    for record in tables.get("PROJWBS", []):
        wbs_id = _clean_text(record.get("wbs_id"))
        parent_wbs_id = _clean_text(record.get("parent_wbs_id")) or None
        node = WBSNode(
            wbs_id=wbs_id,
            parent_wbs_id=parent_wbs_id,
            short_name=_clean_text(record.get("wbs_short_name")),
            name=_clean_text(record.get("wbs_name")),
        )
        wbs_by_id[wbs_id] = node
        children_by_parent[parent_wbs_id].append(wbs_id)

    return wbs_by_id, dict(children_by_parent)


def _parse_tasks(tables: dict[str, list[dict[str, str]]]) -> list[TaskRecord]:
    tasks: list[TaskRecord] = []

    for record in tables.get("TASK", []):
        tasks.append(
            TaskRecord(
                task_id=_clean_text(record.get("task_id")),
                wbs_id=_clean_text(record.get("wbs_id")),
                task_code=_clean_text(record.get("task_code")),
                task_name=_clean_text(record.get("task_name")),
                status_code=_clean_text(record.get("status_code")),
                total_duration_hours=_parse_float(record.get("target_drtn_hr_cnt")),
                remaining_duration_hours=max(0.0, _parse_float(record.get("remain_drtn_hr_cnt"))),
                physical_percent_complete=_parse_float(record.get("phys_complete_pct")),
                act_start=_parse_datetime(record.get("act_start_date")),
                act_end=_parse_datetime(record.get("act_end_date")),
                target_start=_parse_datetime(record.get("target_start_date")),
                target_end=_parse_datetime(record.get("target_end_date")),
                early_start=_parse_datetime(record.get("early_start_date")),
                early_end=_parse_datetime(record.get("early_end_date")),
            )
        )

    return tasks


def _parse_datetime(value: str | None) -> datetime | None:
    cleaned = _clean_text(value)
    if not cleaned or cleaned in EMPTY_DATE_VALUES:
        return None
    return datetime.strptime(cleaned, DATETIME_FORMAT)


def _parse_float(value: str | None) -> float:
    cleaned = _clean_text(value)
    if not cleaned:
        return 0.0
    return float(cleaned)


def _clean_text(value: str | None) -> str:
    return (value or "").strip()
