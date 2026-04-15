from __future__ import annotations

import csv
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .analysis import analyze_schedules
from .models import AnalysisRow


class AnalyzerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("P6 XER EVM Analyzer")
        self.geometry("1360x820")
        self.minsize(980, 620)

        self.baseline_path = tk.StringVar()
        self.current_path = tk.StringVar()
        self.status_text = tk.StringVar(value="Select two XER files and add one or more WBS search rows.")

        self.main_canvas: tk.Canvas | None = None
        self.main_canvas_window_id: int | None = None
        self.wbs_row_container: ttk.Frame | None = None
        self.wbs_entries: list[tuple[ttk.Frame, ttk.Entry]] = []
        self.results: list[AnalysisRow] = []
        self.spi_tree: ttk.Treeview | None = None
        self.chart_canvas: tk.Canvas | None = None
        self.span_chart_canvas: tk.Canvas | None = None

        self._configure_styles()
        self._build_layout()
        self.add_wbs_row()

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        self.configure(background="#eef3f1")
        style.configure("Root.TFrame", background="#eef3f1")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("Chart.TFrame", background="#f7faf8")
        style.configure("Title.TLabel", background="#eef3f1", foreground="#143b2d", font=("Helvetica", 22, "bold"))
        style.configure("Body.TLabel", background="#ffffff", foreground="#1d2b25", font=("Helvetica", 11))
        style.configure("Hint.TLabel", background="#eef3f1", foreground="#50635a", font=("Helvetica", 10))
        style.configure("ChartTitle.TLabel", background="#ffffff", foreground="#143b2d", font=("Helvetica", 12, "bold"))
        style.configure("Treeview.Heading", font=("Helvetica", 10, "bold"))
        style.configure("Treeview", rowheight=24, font=("Helvetica", 10))

    def _build_layout(self) -> None:
        shell = ttk.Frame(self, style="Root.TFrame")
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(0, weight=1)

        self.main_canvas = tk.Canvas(
            shell,
            background="#eef3f1",
            highlightthickness=0,
        )
        outer_scroll_y = ttk.Scrollbar(shell, orient="vertical", command=self.main_canvas.yview)
        self.main_canvas.configure(yscrollcommand=outer_scroll_y.set)
        self.main_canvas.grid(row=0, column=0, sticky="nsew")
        outer_scroll_y.grid(row=0, column=1, sticky="ns")

        root = ttk.Frame(self.main_canvas, padding=20, style="Root.TFrame")
        self.main_canvas_window_id = self.main_canvas.create_window((0, 0), window=root, anchor="nw")
        root.bind("<Configure>", self._sync_main_scrollregion)
        self.main_canvas.bind("<Configure>", self._sync_main_canvas_width)
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_mousewheel, add="+")
        self.bind_all("<Button-5>", self._on_mousewheel, add="+")

        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)

        header = ttk.Frame(root, style="Root.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="P6 XER EVM Analyzer", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Compare duration-weighted baseline planned progress against duration-weighted current actual progress for matched WBS branches.",
            style="Hint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        input_panel = ttk.Frame(root, padding=16, style="Panel.TFrame")
        input_panel.grid(row=1, column=0, sticky="ew")
        input_panel.columnconfigure(1, weight=1)
        input_panel.columnconfigure(3, weight=1)
        input_panel.columnconfigure(0, minsize=120)
        input_panel.columnconfigure(2, minsize=120)

        ttk.Label(input_panel, text="Baseline XER", style="Body.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Entry(input_panel, textvariable=self.baseline_path).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(0, 8))
        ttk.Button(input_panel, text="Browse", command=lambda: self._browse_file(self.baseline_path)).grid(
            row=0, column=2, sticky="ew", pady=(0, 8)
        )

        ttk.Label(input_panel, text="Current XER", style="Body.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Entry(input_panel, textvariable=self.current_path).grid(row=1, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(input_panel, text="Browse", command=lambda: self._browse_file(self.current_path)).grid(
            row=1, column=2, sticky="ew"
        )

        ttk.Label(
            input_panel,
            text="WBS search rows",
            style="Body.TLabel",
        ).grid(row=2, column=0, sticky="nw", pady=(18, 6))

        self.wbs_row_container = ttk.Frame(input_panel, style="Panel.TFrame")
        self.wbs_row_container.grid(row=2, column=1, columnspan=2, sticky="ew", pady=(18, 6))
        self.wbs_row_container.columnconfigure(0, weight=1)

        controls = ttk.Frame(input_panel, style="Panel.TFrame")
        controls.grid(row=3, column=1, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(controls, text="Add WBS Row", command=self.add_wbs_row).pack(side="left")
        ttk.Button(controls, text="Run Analysis", command=self.run_analysis).pack(side="left", padx=(10, 0))
        ttk.Button(controls, text="Export CSV", command=self.export_results).pack(side="left", padx=(10, 0))

        ttk.Label(root, textvariable=self.status_text, style="Hint.TLabel").grid(row=2, column=0, sticky="sw", pady=(14, 6))

        results_panel = ttk.Frame(root, padding=12, style="Panel.TFrame")
        results_panel.grid(row=3, column=0, sticky="nsew")
        results_panel.columnconfigure(0, weight=1)
        results_panel.rowconfigure(1, weight=1, minsize=260)
        results_panel.rowconfigure(4, weight=0, minsize=420)
        results_panel.rowconfigure(6, weight=0, minsize=420)
        results_panel.rowconfigure(8, weight=0, minsize=190)

        columns = (
            "search_term",
            "matched_wbs",
            "matched_wbs_name",
            "baseline_total",
            "baseline_planned",
            "baseline_percent",
            "current_total",
            "current_actual",
            "current_percent",
            "spi",
            "current_finish",
            "remaining_span",
            "revised_remaining_span",
            "revised_finish",
            "variance",
            "baseline_tasks",
            "current_tasks",
            "path",
        )

        self.tree = ttk.Treeview(results_panel, columns=columns, show="headings")
        headings = {
            "search_term": "Search Term",
            "matched_wbs": "Matched WBS",
            "matched_wbs_name": "WBS Name",
            "baseline_total": "Baseline Activity Sum (days)",
            "baseline_planned": "Baseline Planned Activity Sum (days)",
            "baseline_percent": "Baseline Planned % (Duration-Weighted)",
            "current_total": "Current Activity Sum (days)",
            "current_actual": "Current Actualized Activity Sum (days)",
            "current_percent": "Current Actual % (Duration-Weighted)",
            "spi": "SPI",
            "current_finish": "Current Forecast Finish",
            "remaining_span": "Current Remaining Working Span (days)",
            "revised_remaining_span": "SPI-Revised Remaining Working Span (days)",
            "revised_finish": "SPI-Revised Finish",
            "variance": "Variance (pp)",
            "baseline_tasks": "Baseline Tasks",
            "current_tasks": "Current Tasks",
            "path": "WBS Path",
        }
        widths = {
            "search_term": 160,
            "matched_wbs": 110,
            "matched_wbs_name": 220,
            "baseline_total": 175,
            "baseline_planned": 210,
            "baseline_percent": 220,
            "current_total": 165,
            "current_actual": 225,
            "current_percent": 215,
            "spi": 85,
            "current_finish": 130,
            "remaining_span": 220,
            "revised_remaining_span": 250,
            "revised_finish": 130,
            "variance": 110,
            "baseline_tasks": 110,
            "current_tasks": 110,
            "path": 360,
        }

        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], stretch=column == "path", anchor="center")

        y_scroll = ttk.Scrollbar(results_panel, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(results_panel, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        detail_header = ttk.Frame(results_panel, style="Panel.TFrame")
        detail_header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        detail_header.columnconfigure(0, weight=1)
        ttk.Label(detail_header, text="Detailed Results", style="ChartTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            detail_header,
            text="Full detail table with activity sums, percentages, SPI, finish dates, and matched WBS paths.",
            style="Hint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.tree.grid(row=1, column=0, sticky="nsew")
        y_scroll.grid(row=1, column=1, sticky="ns")
        x_scroll.grid(row=2, column=0, sticky="ew")

        chart_header = ttk.Frame(results_panel, style="Panel.TFrame")
        chart_header.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(14, 8))
        chart_header.columnconfigure(0, weight=1)
        ttk.Label(chart_header, text="Progress Percentage Chart", style="ChartTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            chart_header,
            text="Blue = baseline planned progress %, green = current actual progress %. Percentages are based on summed activity durations.",
            style="Hint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        chart_panel = ttk.Frame(results_panel, padding=8, style="Chart.TFrame")
        chart_panel.grid(row=4, column=0, columnspan=2, sticky="nsew")
        chart_panel.columnconfigure(0, weight=1)
        chart_panel.rowconfigure(0, weight=1)

        self.chart_canvas = tk.Canvas(
            chart_panel,
            background="#f7faf8",
            highlightthickness=0,
            height=380,
        )
        chart_scroll_x = ttk.Scrollbar(chart_panel, orient="horizontal", command=self.chart_canvas.xview)
        self.chart_canvas.configure(xscrollcommand=chart_scroll_x.set)
        self.chart_canvas.grid(row=0, column=0, sticky="nsew")
        chart_scroll_x.grid(row=1, column=0, sticky="ew")
        self.chart_canvas.bind("<Configure>", self._on_percentage_chart_resize)
        self._draw_percentage_chart([])

        span_chart_header = ttk.Frame(results_panel, style="Panel.TFrame")
        span_chart_header.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(14, 8))
        span_chart_header.columnconfigure(0, weight=1)
        ttk.Label(span_chart_header, text="Remaining Span Forecast Comparison", style="ChartTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            span_chart_header,
            text="Blue = current remaining working days, orange = SPI-revised remaining working days. Monday-Friday assumption; baseline is used only to derive SPI.",
            style="Hint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        span_chart_panel = ttk.Frame(results_panel, padding=8, style="Chart.TFrame")
        span_chart_panel.grid(row=6, column=0, columnspan=2, sticky="nsew")
        span_chart_panel.columnconfigure(0, weight=1)
        span_chart_panel.rowconfigure(0, weight=1)

        self.span_chart_canvas = tk.Canvas(
            span_chart_panel,
            background="#f7faf8",
            highlightthickness=0,
            height=380,
        )
        span_chart_scroll_x = ttk.Scrollbar(span_chart_panel, orient="horizontal", command=self.span_chart_canvas.xview)
        self.span_chart_canvas.configure(xscrollcommand=span_chart_scroll_x.set)
        self.span_chart_canvas.grid(row=0, column=0, sticky="nsew")
        span_chart_scroll_x.grid(row=1, column=0, sticky="ew")
        self.span_chart_canvas.bind("<Configure>", self._on_span_chart_resize)
        self._draw_span_chart([])

        spi_header = ttk.Frame(results_panel, style="Panel.TFrame")
        spi_header.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(14, 8))
        spi_header.columnconfigure(0, weight=1)
        ttk.Label(spi_header, text="SPI Summary", style="ChartTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            spi_header,
            text="Compact WBS view for planned %, actual %, SPI, current forecast finish, and SPI-trend finish expectation.",
            style="Hint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        spi_panel = ttk.Frame(results_panel, padding=8, style="Chart.TFrame")
        spi_panel.grid(row=8, column=0, columnspan=2, sticky="nsew")
        spi_panel.columnconfigure(0, weight=1)
        spi_panel.rowconfigure(0, weight=1)

        spi_columns = (
            "wbs_name",
            "planned_percent",
            "actual_percent",
            "spi",
            "current_finish",
            "expected_finish",
        )
        self.spi_tree = ttk.Treeview(spi_panel, columns=spi_columns, show="headings", height=6)
        spi_headings = {
            "wbs_name": "WBS Name",
            "planned_percent": "Planned %",
            "actual_percent": "Actual %",
            "spi": "SPI",
            "current_finish": "Current Forecast Finish",
            "expected_finish": "Expected Finish (SPI Trend)",
        }
        spi_widths = {
            "wbs_name": 320,
            "planned_percent": 95,
            "actual_percent": 95,
            "spi": 80,
            "current_finish": 135,
            "expected_finish": 165,
        }
        for column in spi_columns:
            self.spi_tree.heading(column, text=spi_headings[column])
            self.spi_tree.column(column, width=spi_widths[column], anchor="center")

        spi_y_scroll = ttk.Scrollbar(spi_panel, orient="vertical", command=self.spi_tree.yview)
        spi_x_scroll = ttk.Scrollbar(spi_panel, orient="horizontal", command=self.spi_tree.xview)
        self.spi_tree.configure(yscrollcommand=spi_y_scroll.set, xscrollcommand=spi_x_scroll.set)
        self.spi_tree.grid(row=0, column=0, sticky="nsew")
        spi_y_scroll.grid(row=0, column=1, sticky="ns")
        spi_x_scroll.grid(row=1, column=0, sticky="ew")

    def add_wbs_row(self, value: str = "") -> None:
        if self.wbs_row_container is None:
            return
        row = ttk.Frame(self.wbs_row_container, style="Panel.TFrame")
        row.grid(column=0, sticky="ew", pady=4)
        row.columnconfigure(0, weight=1)

        entry = ttk.Entry(row)
        entry.insert(0, value)
        entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(row, text="Delete", command=lambda frame=row: self.remove_wbs_row(frame)).grid(
            row=0, column=1, padx=(8, 0)
        )
        self.wbs_entries.append((row, entry))

    def remove_wbs_row(self, frame: ttk.Frame) -> None:
        if len(self.wbs_entries) == 1:
            self.wbs_entries[0][1].delete(0, tk.END)
            return

        for index, (stored_frame, _) in enumerate(self.wbs_entries):
            if stored_frame == frame:
                stored_frame.destroy()
                del self.wbs_entries[index]
                break

    def run_analysis(self) -> None:
        baseline = self.baseline_path.get().strip()
        current = self.current_path.get().strip()
        search_terms = [entry.get().strip() for _, entry in self.wbs_entries if entry.get().strip()]

        if not baseline or not current:
            messagebox.showerror("Missing File", "Select both the baseline and current XER files.")
            return
        if not search_terms:
            messagebox.showerror("Missing WBS", "Add at least one WBS search row before running the analysis.")
            return

        try:
            rows, baseline_schedule, current_schedule = analyze_schedules(baseline, current, search_terms)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Analysis Failed", str(exc))
            self.status_text.set("Analysis failed. Check the selected files and search inputs.")
            return

        self.results = rows
        self._populate_spi_summary(rows)
        self._populate_results(rows)
        self._draw_percentage_chart(rows)
        self._draw_span_chart(rows)

        if rows:
            self.status_text.set(
                "Analysis complete. "
                f"Baseline data date is {baseline_schedule.project.data_date:%Y-%m-%d %H:%M}; "
                f"current data date is {current_schedule.project.data_date:%Y-%m-%d %H:%M}."
            )
        else:
            self.status_text.set(
                "No matching WBS rows were found in either schedule for the current search terms."
            )

    def export_results(self) -> None:
        if not self.results:
            messagebox.showinfo("No Results", "Run an analysis before exporting.")
            return

        output_path = filedialog.asksaveasfilename(
            title="Export Results",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
        )
        if not output_path:
            return

        with Path(output_path).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "search_term",
                    "matched_wbs",
                    "matched_wbs_name",
                    "matched_wbs_path",
                    "baseline_activity_sum_days",
                    "baseline_planned_activity_sum_days",
                    "baseline_planned_percent_duration_weighted",
                    "current_activity_sum_days",
                    "current_actualized_activity_sum_days",
                    "current_actual_percent_duration_weighted",
                    "spi",
                    "current_forecast_finish",
                    "current_remaining_span_days",
                    "revised_remaining_span_days",
                    "revised_finish_date",
                    "variance_percent_points",
                    "baseline_task_count",
                    "current_task_count",
                ]
            )
            for row in self.results:
                writer.writerow(
                    [
                        row.search_term,
                        row.matched_wbs,
                        row.matched_wbs_name,
                        row.matched_wbs_path,
                        f"{row.baseline_total_days:.2f}",
                        f"{row.baseline_planned_days:.2f}",
                        f"{row.baseline_planned_percent:.2f}",
                        f"{row.current_total_days:.2f}",
                        f"{row.current_actual_days:.2f}",
                        f"{row.current_actual_percent:.2f}",
                        _format_float(row.spi),
                        _format_date(row.current_forecast_finish),
                        f"{row.current_remaining_span_days:.2f}",
                        _format_float(row.revised_remaining_span_days),
                        _format_date(row.revised_finish_date),
                        f"{row.variance_percent_points:.2f}",
                        row.baseline_task_count,
                        row.current_task_count,
                    ]
                )

        self.status_text.set(f"Results exported to {output_path}")

    def _populate_results(self, rows: list[AnalysisRow]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        for row in rows:
            self.tree.insert(
                "",
                "end",
                values=(
                    row.search_term,
                    row.matched_wbs,
                    row.matched_wbs_name,
                    f"{row.baseline_total_days:.2f}",
                    f"{row.baseline_planned_days:.2f}",
                    f"{row.baseline_planned_percent:.2f}",
                    f"{row.current_total_days:.2f}",
                    f"{row.current_actual_days:.2f}",
                    f"{row.current_actual_percent:.2f}",
                    _format_float(row.spi),
                    _format_date(row.current_forecast_finish),
                    f"{row.current_remaining_span_days:.2f}",
                    _format_float(row.revised_remaining_span_days),
                    _format_date(row.revised_finish_date),
                    f"{row.variance_percent_points:.2f}",
                    row.baseline_task_count,
                    row.current_task_count,
                    row.matched_wbs_path,
                ),
            )

    def _populate_spi_summary(self, rows: list[AnalysisRow]) -> None:
        if self.spi_tree is None:
            return

        for item in self.spi_tree.get_children():
            self.spi_tree.delete(item)

        for row in rows:
            self.spi_tree.insert(
                "",
                "end",
                values=(
                    row.matched_wbs_name,
                    f"{row.baseline_planned_percent:.2f}",
                    f"{row.current_actual_percent:.2f}",
                    _format_float(row.spi),
                    _format_date(row.current_forecast_finish),
                    _format_date(row.revised_finish_date),
                ),
            )

    def _on_percentage_chart_resize(self, event: tk.Event[tk.Misc]) -> None:
        if event.width > 0 and event.height > 0:
            self._draw_percentage_chart(self.results, canvas_width=event.width, canvas_height=event.height)

    def _on_span_chart_resize(self, event: tk.Event[tk.Misc]) -> None:
        if event.width > 0 and event.height > 0:
            self._draw_span_chart(self.results, canvas_width=event.width, canvas_height=event.height)

    def _sync_main_scrollregion(self, _event: tk.Event[tk.Misc]) -> None:
        if self.main_canvas is None:
            return
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

    def _sync_main_canvas_width(self, event: tk.Event[tk.Misc]) -> None:
        if self.main_canvas is None or self.main_canvas_window_id is None:
            return
        self.main_canvas.itemconfigure(self.main_canvas_window_id, width=event.width)

    def _on_mousewheel(self, event: tk.Event[tk.Misc]) -> None:
        if self.main_canvas is None:
            return
        event_num = getattr(event, "num", None)
        if event_num == 4:
            delta = -1
        elif event_num == 5:
            delta = 1
        else:
            delta = int(-event.delta / 120) if getattr(event, "delta", 0) else 0
        if delta != 0:
            self.main_canvas.yview_scroll(delta, "units")

    def _draw_percentage_chart(
        self,
        rows: list[AnalysisRow],
        canvas_width: int | None = None,
        canvas_height: int | None = None,
    ) -> None:
        if self.chart_canvas is None:
            return

        canvas = self.chart_canvas
        visible_width = canvas_width or max(canvas.winfo_width(), 900)
        visible_height = canvas_height or max(canvas.winfo_height(), 380)
        visible_width = max(visible_width, 900)
        visible_height = max(visible_height, 380)
        canvas.delete("all")

        if not rows:
            empty_height = 180
            canvas.create_text(
                visible_width / 2,
                empty_height / 2,
                text="Run an analysis to plot baseline planned % versus current actual %.",
                fill="#5c6e66",
                font=("Helvetica", 12),
            )
            canvas.configure(scrollregion=(0, 0, visible_width, empty_height))
            return

        chart_left = 72
        chart_top = 46
        chart_bottom = visible_height - 96
        chart_height = max(chart_bottom - chart_top, 160)
        group_width = 110
        bar_width = 28
        bar_gap = 10
        group_gap = 32
        chart_width = len(rows) * (group_width + group_gap)
        total_width = max(visible_width, chart_left + chart_width + 60)
        chart_right = total_width - 36
        max_percent = max(
            100.0,
            max(max(row.baseline_planned_percent, row.current_actual_percent) for row in rows),
        )

        tick_count = 5
        for tick in range(tick_count + 1):
            tick_percent = max_percent * tick / tick_count
            y = chart_bottom - chart_height * tick / tick_count
            canvas.create_line(chart_left, y, chart_right, y, fill="#d6e3dd", width=1)
            canvas.create_text(
                chart_left - 12,
                y,
                anchor="e",
                text=f"{tick_percent:.0f}%",
                fill="#70837a",
                font=("Helvetica", 9),
            )

        canvas.create_line(chart_left, chart_top, chart_left, chart_bottom, fill="#7e9088", width=1)
        canvas.create_line(chart_left, chart_bottom, chart_right, chart_bottom, fill="#7e9088", width=1)

        baseline_color = "#377eb8"
        current_color = "#2d8a57"

        for index, row in enumerate(rows):
            group_x0 = chart_left + index * (group_width + group_gap) + 18
            baseline_x0 = group_x0
            baseline_x1 = baseline_x0 + bar_width
            current_x0 = baseline_x1 + bar_gap
            current_x1 = current_x0 + bar_width
            baseline_center = (baseline_x0 + baseline_x1) / 2
            current_center = (current_x0 + current_x1) / 2
            group_center = (baseline_center + current_center) / 2

            baseline_bar_height = chart_height * (row.baseline_planned_percent / max_percent)
            current_bar_height = chart_height * (row.current_actual_percent / max_percent)
            baseline_y0 = chart_bottom - baseline_bar_height
            current_y0 = chart_bottom - current_bar_height

            canvas.create_rectangle(
                baseline_x0,
                baseline_y0,
                baseline_x1,
                chart_bottom,
                fill=baseline_color,
                outline="",
            )
            canvas.create_rectangle(
                current_x0,
                current_y0,
                current_x1,
                chart_bottom,
                fill=current_color,
                outline="",
            )

            canvas.create_text(
                baseline_center,
                max(chart_top + 12, baseline_y0 - 14),
                text=f"{row.baseline_planned_percent:.1f}%",
                fill="#17352b",
                font=("Helvetica", 9),
            )
            canvas.create_text(
                current_center,
                max(chart_top + 12, current_y0 - 14),
                text=f"{row.current_actual_percent:.1f}%",
                fill="#17352b",
                font=("Helvetica", 9),
            )

            label_top = chart_bottom + 16
            canvas.create_text(
                group_center,
                label_top,
                anchor="n",
                text=_truncate_label(row.search_term, 16),
                fill="#17352b",
                font=("Helvetica", 10, "bold"),
            )
            canvas.create_text(
                group_center,
                label_top + 18,
                anchor="n",
                text=_truncate_label(row.matched_wbs, 18),
                fill="#567066",
                font=("Helvetica", 9),
            )

        legend_y = visible_height - 18
        canvas.create_rectangle(20, legend_y - 10, 34, legend_y + 4, fill=baseline_color, outline="")
        canvas.create_text(42, legend_y - 3, anchor="w", text="Baseline planned progress %", fill="#17352b", font=("Helvetica", 9))
        canvas.create_rectangle(180, legend_y - 10, 194, legend_y + 4, fill=current_color, outline="")
        canvas.create_text(202, legend_y - 3, anchor="w", text="Current actual progress %", fill="#17352b", font=("Helvetica", 9))

        canvas.configure(scrollregion=(0, 0, total_width, visible_height))

    def _draw_span_chart(
        self,
        rows: list[AnalysisRow],
        canvas_width: int | None = None,
        canvas_height: int | None = None,
    ) -> None:
        if self.span_chart_canvas is None:
            return

        canvas = self.span_chart_canvas
        visible_width = canvas_width or max(canvas.winfo_width(), 900)
        visible_height = canvas_height or max(canvas.winfo_height(), 380)
        visible_width = max(visible_width, 900)
        visible_height = max(visible_height, 380)
        canvas.delete("all")

        if not rows:
            empty_height = 180
            canvas.create_text(
                visible_width / 2,
                empty_height / 2,
                text="Run an analysis to plot current versus SPI-revised remaining WBS span days.",
                fill="#5c6e66",
                font=("Helvetica", 12),
            )
            canvas.configure(scrollregion=(0, 0, visible_width, empty_height))
            return

        chart_left = 72
        chart_top = 46
        chart_bottom = visible_height - 96
        chart_height = max(chart_bottom - chart_top, 160)
        group_width = 110
        bar_width = 28
        bar_gap = 10
        group_gap = 32
        chart_width = len(rows) * (group_width + group_gap)
        total_width = max(visible_width, chart_left + chart_width + 60)
        chart_right = total_width - 36
        max_value = max(
            1.0,
            max(
                max(
                    row.current_remaining_span_days,
                    row.revised_remaining_span_days or 0.0,
                )
                for row in rows
            ),
        )

        tick_count = 5
        for tick in range(tick_count + 1):
            tick_value = max_value * tick / tick_count
            y = chart_bottom - chart_height * tick / tick_count
            canvas.create_line(chart_left, y, chart_right, y, fill="#d6e3dd", width=1)
            canvas.create_text(
                chart_left - 12,
                y,
                anchor="e",
                text=f"{tick_value:.0f}",
                fill="#70837a",
                font=("Helvetica", 9),
            )

        canvas.create_line(chart_left, chart_top, chart_left, chart_bottom, fill="#7e9088", width=1)
        canvas.create_line(chart_left, chart_bottom, chart_right, chart_bottom, fill="#7e9088", width=1)

        current_color = "#2f6fb0"
        revised_color = "#cf7a1b"

        for index, row in enumerate(rows):
            group_x0 = chart_left + index * (group_width + group_gap) + 18
            current_x0 = group_x0
            current_x1 = current_x0 + bar_width
            revised_x0 = current_x1 + bar_gap
            revised_x1 = revised_x0 + bar_width
            current_center = (current_x0 + current_x1) / 2
            revised_center = (revised_x0 + revised_x1) / 2
            group_center = (current_center + revised_center) / 2

            current_bar_height = chart_height * (row.current_remaining_span_days / max_value)
            current_y0 = chart_bottom - current_bar_height
            canvas.create_rectangle(
                current_x0,
                current_y0,
                current_x1,
                chart_bottom,
                fill=current_color,
                outline="",
            )
            canvas.create_text(
                current_center,
                max(chart_top + 12, current_y0 - 14),
                text=f"{row.current_remaining_span_days:.1f}",
                fill="#17352b",
                font=("Helvetica", 9),
            )

            if row.revised_remaining_span_days is not None:
                revised_bar_height = chart_height * (row.revised_remaining_span_days / max_value)
                revised_y0 = chart_bottom - revised_bar_height
                canvas.create_rectangle(
                    revised_x0,
                    revised_y0,
                    revised_x1,
                    chart_bottom,
                    fill=revised_color,
                    outline="",
                )
                canvas.create_text(
                    revised_center,
                    max(chart_top + 12, revised_y0 - 14),
                    text=f"{row.revised_remaining_span_days:.1f}",
                    fill="#17352b",
                    font=("Helvetica", 9),
                )
            else:
                canvas.create_text(
                    revised_center,
                    chart_bottom - 12,
                    text="N/A",
                    fill="#9a5e1d",
                    font=("Helvetica", 9, "bold"),
                )

            label_top = chart_bottom + 16
            canvas.create_text(
                group_center,
                label_top,
                anchor="n",
                text=_truncate_label(row.search_term, 16),
                fill="#17352b",
                font=("Helvetica", 10, "bold"),
            )
            canvas.create_text(
                group_center,
                label_top + 18,
                anchor="n",
                text=_truncate_label(row.matched_wbs, 18),
                fill="#567066",
                font=("Helvetica", 9),
            )

        legend_y = visible_height - 18
        canvas.create_rectangle(20, legend_y - 10, 34, legend_y + 4, fill=current_color, outline="")
        canvas.create_text(42, legend_y - 3, anchor="w", text="Current remaining working days", fill="#17352b", font=("Helvetica", 9))
        canvas.create_rectangle(200, legend_y - 10, 214, legend_y + 4, fill=revised_color, outline="")
        canvas.create_text(222, legend_y - 3, anchor="w", text="SPI-revised remaining working days", fill="#17352b", font=("Helvetica", 9))

        canvas.configure(scrollregion=(0, 0, total_width, visible_height))

    def _browse_file(self, variable: tk.StringVar) -> None:
        selected = filedialog.askopenfilename(
            title="Select XER File",
            filetypes=[("Primavera XER Files", "*.xer"), ("All Files", "*.*")],
        )
        if selected:
            variable.set(selected)


def _truncate_label(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 3]}..."


def _format_float(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def _format_date(value: object) -> str:
    if value is None:
        return "N/A"
    return value.strftime("%Y-%m-%d")


def run() -> None:
    app = AnalyzerApp()
    app.mainloop()
