from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

from .models import AnalysisRow, ScheduleData, TaskRecord, WBSMatch
from .xer_parser import parse_xer_file


def analyze_schedules(
    baseline_path: str | Path,
    current_path: str | Path,
    search_terms: list[str],
) -> tuple[list[AnalysisRow], ScheduleData, ScheduleData]:
    cleaned_terms = [term.strip() for term in search_terms if term.strip()]
    if not cleaned_terms:
        raise ValueError("At least one WBS search term is required.")

    baseline_schedule = parse_xer_file(baseline_path)
    current_schedule = parse_xer_file(current_path)

    baseline_matches = _find_wbs_matches(baseline_schedule, cleaned_terms)
    current_matches = _find_wbs_matches(current_schedule, cleaned_terms)
    rows: list[AnalysisRow] = []

    for search_term in cleaned_terms:
        baseline_term_matches = [match for match in baseline_matches if match.search_term == search_term]
        current_term_matches = [match for match in current_matches if match.search_term == search_term]

        if not baseline_term_matches and not current_term_matches:
            continue

        baseline_scope = _collect_scope_for_matches(baseline_schedule, baseline_term_matches)
        current_scope = _collect_scope_for_matches(current_schedule, current_term_matches)

        baseline_tasks = _tasks_for_scope(baseline_schedule.tasks, baseline_scope)
        current_tasks = _tasks_for_scope(current_schedule.tasks, current_scope)

        baseline_total = sum(task.total_duration_hours for task in baseline_tasks)
        baseline_planned = sum(
            _planned_duration_by_date(task, current_schedule.project.data_date) for task in baseline_tasks
        )
        current_total = sum(task.total_duration_hours for task in current_tasks)
        current_actual = sum(_actualized_duration(task) for task in current_tasks)

        baseline_percent = _safe_percent(baseline_planned, baseline_total)
        current_percent = _safe_percent(current_actual, current_total)
        spi = _calculate_spi(current_percent, baseline_percent)
        current_forecast_finish = _wbs_current_forecast_finish(current_tasks, current_schedule.project.data_date)
        current_remaining_span_days = _remaining_working_span_days(
            current_schedule.project.data_date,
            current_forecast_finish,
        )
        revised_remaining_span_days = _revised_remaining_span_days(current_remaining_span_days, spi)
        revised_finish_date = _revised_finish_date(
            current_schedule.project.data_date,
            current_forecast_finish,
            revised_remaining_span_days,
        )

        rows.append(
            AnalysisRow(
                search_term=search_term,
                matched_wbs=_summarize_match_codes(current_term_matches or baseline_term_matches),
                matched_wbs_name=_summarize_match_names(current_term_matches or baseline_term_matches),
                matched_wbs_path=_summarize_match_paths(current_term_matches, baseline_term_matches),
                baseline_total_days=_hours_to_days(
                    baseline_total,
                    baseline_schedule.project.default_day_hours,
                ),
                baseline_planned_days=_hours_to_days(
                    baseline_planned,
                    baseline_schedule.project.default_day_hours,
                ),
                baseline_planned_percent=baseline_percent,
                current_total_days=_hours_to_days(
                    current_total,
                    current_schedule.project.default_day_hours,
                ),
                current_actual_days=_hours_to_days(
                    current_actual,
                    current_schedule.project.default_day_hours,
                ),
                current_actual_percent=current_percent,
                spi=spi,
                current_forecast_finish=current_forecast_finish,
                current_remaining_span_days=current_remaining_span_days,
                revised_remaining_span_days=revised_remaining_span_days,
                revised_finish_date=revised_finish_date,
                variance_percent_points=current_percent - baseline_percent,
                baseline_task_count=len(baseline_tasks),
                current_task_count=len(current_tasks),
            )
        )

    return rows, baseline_schedule, current_schedule


def _find_wbs_matches(schedule: ScheduleData, search_terms: list[str]) -> list[WBSMatch]:
    matches: list[WBSMatch] = []

    for search_term in search_terms:
        normalized_term = search_term.casefold()
        for node in schedule.wbs_by_id.values():
            if not _wbs_matches_term(node.short_name, node.name, normalized_term):
                continue
            matches.append(
                WBSMatch(
                    search_term=search_term,
                    wbs_id=node.wbs_id,
                    short_name=node.short_name,
                    name=node.name,
                    path=_build_wbs_path(schedule, node.wbs_id),
                )
            )

    return matches


def _wbs_matches_term(short_name: str, name: str, normalized_term: str) -> bool:
    return normalized_term in short_name.casefold() or normalized_term in name.casefold()


def _build_wbs_path(schedule: ScheduleData, starting_wbs_id: str) -> str:
    segments: list[str] = []
    current_id: str | None = starting_wbs_id

    while current_id:
        node = schedule.wbs_by_id.get(current_id)
        if node is None:
            break
        label = _wbs_label(node.short_name, node.name, current_id)
        segments.append(label)
        current_id = node.parent_wbs_id

    ordered = list(reversed(segments))
    if len(ordered) > 1:
        ordered = ordered[1:]
    return " / ".join(ordered)
def _wbs_label(short_name: str, name: str, fallback: str) -> str:
    if short_name and name and short_name != name:
        return f"{short_name} - {name}"
    return name or short_name or fallback


def _collect_descendant_wbs_ids(schedule: ScheduleData, root_wbs_id: str) -> set[str]:
    collected: set[str] = set()
    stack = [root_wbs_id]

    while stack:
        current_id = stack.pop()
        if current_id in collected:
            continue
        collected.add(current_id)
        stack.extend(schedule.children_by_parent.get(current_id, []))

    return collected


def _collect_scope_for_matches(schedule: ScheduleData, matches: list[WBSMatch]) -> set[str]:
    scope: set[str] = set()
    for match in matches:
        scope.update(_collect_descendant_wbs_ids(schedule, match.wbs_id))
    return scope


def _tasks_for_scope(tasks: list[TaskRecord], scope_wbs_ids: set[str]) -> list[TaskRecord]:
    seen_task_ids: set[str] = set()
    scoped_tasks: list[TaskRecord] = []

    for task in tasks:
        if task.wbs_id not in scope_wbs_ids or task.task_id in seen_task_ids:
            continue
        scoped_tasks.append(task)
        seen_task_ids.add(task.task_id)

    return scoped_tasks


def _summarize_match_codes(matches: list[WBSMatch]) -> str:
    codes = _unique_preserving_order(match.short_name or match.name for match in matches)
    if not codes:
        return "No match"
    if len(codes) == 1:
        return codes[0]
    return f"{len(codes)} matched WBSs"


def _summarize_match_names(matches: list[WBSMatch]) -> str:
    names = _unique_preserving_order(match.name or match.short_name for match in matches)
    if not names:
        return "No match"
    if len(names) <= 3:
        return " | ".join(names)
    return f"{names[0]} | {names[1]} | {names[2]} | +{len(names) - 3} more"


def _summarize_match_paths(
    current_matches: list[WBSMatch],
    baseline_matches: list[WBSMatch],
) -> str:
    current_paths = _unique_preserving_order(match.path for match in current_matches)
    baseline_paths = _unique_preserving_order(match.path for match in baseline_matches)

    if current_paths and baseline_paths:
        current_summary = _truncate_joined_values(current_paths)
        baseline_summary = _truncate_joined_values(baseline_paths)
        return f"Current: {current_summary} || Baseline: {baseline_summary}"
    if current_paths:
        return f"Current: {_truncate_joined_values(current_paths)}"
    if baseline_paths:
        return f"Baseline: {_truncate_joined_values(baseline_paths)}"
    return "No matched WBS path"


def _truncate_joined_values(values: list[str], limit: int = 2) -> str:
    if len(values) <= limit:
        return " | ".join(values)
    return f"{' | '.join(values[:limit])} | +{len(values) - limit} more"


def _unique_preserving_order(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique_values.append(cleaned)
    return unique_values


def _planned_duration_by_date(task: TaskRecord, data_date: datetime) -> float:
    total = task.total_duration_hours
    if total <= 0:
        return 0.0

    start = task.target_start or task.early_start
    end = task.target_end or task.early_end
    if start is None or end is None:
        return 0.0

    if data_date <= start:
        return 0.0
    if data_date >= end:
        return total

    total_seconds = (end - start).total_seconds()
    if total_seconds <= 0:
        return total if data_date >= end else 0.0

    elapsed_seconds = (data_date - start).total_seconds()
    ratio = min(1.0, max(0.0, elapsed_seconds / total_seconds))
    return total * ratio


def _actualized_duration(task: TaskRecord) -> float:
    total = task.total_duration_hours
    remaining = min(max(task.remaining_duration_hours, 0.0), max(total, 0.0))
    return max(0.0, total - remaining)


def _safe_percent(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return (numerator / denominator) * 100.0


def _hours_to_days(duration_hours: float, day_hours: float) -> float:
    safe_day_hours = day_hours if day_hours > 0 else 8.0
    return duration_hours / safe_day_hours


def _calculate_spi(actual_percent: float, planned_percent: float) -> float | None:
    if planned_percent <= 0:
        return None
    return actual_percent / planned_percent


def _wbs_current_forecast_finish(tasks: list[TaskRecord], data_date: datetime) -> datetime | None:
    remaining_finishes = [
        finish
        for finish in (_task_forecast_finish(task) for task in tasks if task.remaining_duration_hours > 0)
        if finish is not None
    ]
    if remaining_finishes:
        return max(remaining_finishes)

    completed_finishes = [
        finish
        for finish in (_task_completion_finish(task) for task in tasks)
        if finish is not None
    ]
    if completed_finishes:
        return max(completed_finishes)

    return data_date


def _task_forecast_finish(task: TaskRecord) -> datetime | None:
    return task.early_end or task.target_end or task.act_end


def _task_completion_finish(task: TaskRecord) -> datetime | None:
    return task.act_end or task.early_end or task.target_end


def _remaining_working_span_days(data_date: datetime, forecast_finish: datetime | None) -> float:
    if forecast_finish is None or forecast_finish <= data_date:
        return 0.0
    return _weekday_duration_days(data_date, forecast_finish)


def _revised_remaining_span_days(current_remaining_span_days: float, spi: float | None) -> float | None:
    if current_remaining_span_days <= 0:
        return 0.0
    if spi is None or spi <= 0:
        return None
    return current_remaining_span_days / spi


def _revised_finish_date(
    data_date: datetime,
    current_forecast_finish: datetime | None,
    revised_remaining_span_days: float | None,
) -> datetime | None:
    if revised_remaining_span_days is None:
        return None
    if revised_remaining_span_days <= 0:
        return current_forecast_finish or data_date
    return _add_weekday_duration_days(data_date, revised_remaining_span_days)


def _weekday_duration_days(start: datetime, end: datetime) -> float:
    if end <= start:
        return 0.0

    total_seconds = 0.0
    current = start

    while current < end:
        next_boundary = datetime.combine(current.date() + timedelta(days=1), time.min)
        segment_end = min(next_boundary, end)
        if current.weekday() < 5:
            total_seconds += (segment_end - current).total_seconds()
        current = next_boundary

    return total_seconds / 86400.0


def _add_weekday_duration_days(start: datetime, working_days: float) -> datetime:
    if working_days <= 0:
        return start

    remaining_seconds = working_days * 86400.0
    current = start

    while remaining_seconds > 0:
        if current.weekday() >= 5:
            current = datetime.combine(_next_weekday(current.date()), time.min)
            continue

        next_boundary = datetime.combine(current.date() + timedelta(days=1), time.min)
        available_seconds = (next_boundary - current).total_seconds()
        if remaining_seconds <= available_seconds:
            return current + timedelta(seconds=remaining_seconds)

        remaining_seconds -= available_seconds
        current = next_boundary

    return current


def _next_weekday(day: date) -> date:
    candidate = day + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate
