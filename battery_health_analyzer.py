#!/usr/bin/env python3
"""Battery Health Analyzer GUI.

Architecture overview
---------------------
- Data layer: CSV loading/normalization (`date`, `capacity_percent`) and optional
  one-click capture of current battery status from the host OS.
- Modeling layer: robust linear degradation model using Theil-Sen regression
  (resistant to outliers and suitable for long-term trend extrapolation).
- Presentation layer: Tkinter GUI + Matplotlib timeline for historical values,
  forecast curve, threshold marker, and projected end-of-life date.

Forecast model
--------------
The model estimates battery health as a function of elapsed days:
    health(t) = a + b * t

Where:
- t is days since the first sample.
- a is the estimated initial health intercept.
- b is the degradation slope (typically negative).

End of life is defined as the first date where predicted health is <= threshold
(default: 80%). This is a practical maintenance threshold, not a safety limit.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, ttk

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from sklearn.linear_model import TheilSenRegressor

from battery_logger import BatteryReadError, get_battery_capacity_percent


class BatteryAnalyzer:
    """Interactive battery degradation analyzer and end-of-life forecaster."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Battery Health Analyzer")
        self.root.geometry("980x740")
        self.root.minsize(760, 560)

        self.df: pd.DataFrame | None = None
        self.model: TheilSenRegressor | None = None
        self.base_date: datetime | None = None
        self.end_life_threshold = 80.0

        self._build_layout()
        self._refresh_current_battery_status()
        self._apply_initial_window_size()

    def _build_layout(self) -> None:
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.rowconfigure(2, weight=1)
        main_frame.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(main_frame)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        toolbar.columnconfigure(0, weight=1)
        toolbar.columnconfigure(2, weight=1)

        btn_frame = ttk.Frame(toolbar)
        btn_frame.grid(row=0, column=1)

        button_specs = [
            ("Load Historical CSV", self.load_csv),
            ("Capture Current Battery", self.capture_current),
            ("Generate Sample Data", self.generate_sample),
            ("Plot and Forecast", self.plot_and_predict),
        ]
        for idx, (text, command) in enumerate(button_specs):
            ttk.Button(btn_frame, text=text, command=command).grid(
                row=0, column=idx, padx=5, pady=2, sticky="ew"
            )

        self.status_label = ttk.Label(
            main_frame,
            text="Ready. Load a CSV file, capture current state, or generate sample data.",
            relief=tk.SUNKEN,
            anchor=tk.W,
            wraplength=720,
        )
        self.status_label.grid(row=1, column=0, sticky="ew", pady=5)

        self.figure = plt.Figure(figsize=(9, 5.5), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=main_frame)
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.grid(row=2, column=0, sticky="nsew", pady=10)

        self.result_frame = ttk.LabelFrame(main_frame, text="Battery Lifetime Forecast", padding="8")
        self.result_frame.grid(row=3, column=0, sticky="ew", pady=(0, 5))
        self.result_frame.columnconfigure(0, weight=1)

        self.result_label = ttk.Label(
            self.result_frame,
            text="No forecast has been run yet.",
            font=("Helvetica", 10),
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=760,
        )
        self.result_label.grid(row=0, column=0, sticky="ew")

        main_frame.bind("<Configure>", self._on_main_resize)

    def _on_main_resize(self, event: tk.Event) -> None:
        """Keep long text readable when window size or font scaling changes."""
        content_width = max(360, event.width - 40)
        self.status_label.configure(wraplength=content_width)
        self.result_label.configure(wraplength=content_width)

    def _apply_initial_window_size(self) -> None:
        """Adjust initial geometry to fit content while respecting screen bounds."""
        self.root.update_idletasks()

        req_width = self.root.winfo_reqwidth() + 24
        req_height = self.root.winfo_reqheight() + 24
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        max_w = int(screen_w * 0.96)
        max_h = int(screen_h * 0.90)
        width = min(max(req_width, 900), max_w)
        height = min(max(req_height, 640), max_h)

        pos_x = max(0, (screen_w - width) // 2)
        pos_y = max(0, (screen_h - height) // 3)
        self.root.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    def _refresh_current_battery_status(self) -> None:
        """Read and display current battery health/charge according to platform support."""
        try:
            capacity_percent, source = get_battery_capacity_percent()
            self.status_label.config(
                text=f"Current battery reading: {capacity_percent:.1f}% (source: {source})."
            )
        except BatteryReadError as exc:
            self.status_label.config(text=f"Battery status not available: {exc}")

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize accepted column names to canonical English schema."""
        rename_map = {
            "data": "date",
            "capacidade_percent": "capacity_percent",
            "capacidade": "capacity_percent",
        }

        normalized = df.copy()
        normalized.columns = [c.strip().lower() for c in normalized.columns]
        normalized = normalized.rename(columns=rename_map)

        required = {"date", "capacity_percent"}
        if not required.issubset(set(normalized.columns)):
            raise ValueError(
                "CSV must contain date and capacity_percent columns "
                "(legacy aliases: data, capacidade_percent)."
            )

        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        normalized["capacity_percent"] = pd.to_numeric(normalized["capacity_percent"], errors="coerce")
        normalized = normalized.dropna(subset=["date", "capacity_percent"])

        # Keep realistic values and avoid impossible percentages.
        normalized = normalized[(normalized["capacity_percent"] > 0) & (normalized["capacity_percent"] <= 120)]
        normalized = normalized.sort_values("date")

        return normalized[["date", "capacity_percent"]].reset_index(drop=True)

    def load_csv(self) -> None:
        """Load a CSV file with battery history."""
        file_path = filedialog.askopenfilename(
            title="Select historical CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            raw = pd.read_csv(file_path)
            self.df = self._normalize_columns(raw)
            self.status_label.config(
                text=(
                    f"Loaded {len(self.df)} records from "
                    f"{self.df['date'].min().date()} to {self.df['date'].max().date()}."
                )
            )
            messagebox.showinfo("Success", f"Loaded {len(self.df)} valid records.")
        except Exception as exc:
            messagebox.showerror("Load Error", f"Failed to load CSV:\n{exc}")

    def capture_current(self) -> None:
        """Append one current battery sample to the in-memory history."""
        try:
            capacity_percent, source = get_battery_capacity_percent()
            current_date = datetime.now()
            new_record = pd.DataFrame(
                {"date": [current_date], "capacity_percent": [capacity_percent]}
            )

            if self.df is None:
                self.df = new_record
            else:
                # Keep at most one value per day by replacing same-day entries.
                day_floor = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
                self.df = self.df[self.df["date"] < day_floor]
                self.df = pd.concat([self.df, new_record], ignore_index=True)
                self.df = self.df.sort_values("date")

            self.status_label.config(
                text=(
                    f"Captured current sample: {current_date.strftime('%Y-%m-%d')} -> "
                    f"{capacity_percent:.1f}% ({source})."
                )
            )
            messagebox.showinfo("Captured", f"Current battery value: {capacity_percent:.1f}%\nSource: {source}")
        except BatteryReadError as exc:
            messagebox.showerror("Capture Error", f"Could not read battery status:\n{exc}")

    def generate_sample(self) -> None:
        """Generate synthetic two-year battery history for demo/testing."""
        start_date = datetime.now() - timedelta(days=730)
        dates = [start_date + timedelta(days=i) for i in range(0, 730, 7)]
        days = np.array([(d - start_date).days for d in dates])

        # Exponential-like decay with light noise to emulate field data.
        capacity = 100 * np.exp(-days / 1700)
        rng = np.random.default_rng(42)
        capacity += rng.normal(0, 0.8, size=len(capacity))
        capacity = np.clip(capacity, 65, 100)

        self.df = pd.DataFrame({"date": dates, "capacity_percent": capacity})
        self.status_label.config(text=f"Generated {len(self.df)} synthetic records.")
        messagebox.showinfo("Sample Data", "Sample dataset generated. Click 'Plot and Forecast'.")

    def train_model(self) -> bool:
        """Train robust linear trend model for long-range extrapolation."""
        if self.df is None:
            messagebox.showerror("Model Error", "No data loaded.")
            return False

        if len(self.df) < 4:
            messagebox.showerror(
                "Model Error",
                f"Insufficient data. Found {len(self.df)} valid records; at least 4 are required.",
            )
            return False

        self.base_date = self.df["date"].min().to_pydatetime()
        elapsed_days = (self.df["date"] - self.base_date).dt.total_seconds() / 86400.0
        if elapsed_days.nunique() < 2:
            messagebox.showerror(
                "Model Error",
                "Insufficient time span. Need records with at least 2 different timestamps.",
            )
            return False

        x = elapsed_days.to_numpy().reshape(-1, 1)
        y = self.df["capacity_percent"].to_numpy()

        self.model = TheilSenRegressor(random_state=42)
        self.model.fit(x, y)
        return True

    def predict_future(self) -> tuple[np.ndarray, list[datetime], datetime | None]:
        """Predict health curve and end-of-life date based on threshold crossing."""
        if self.model is None and not self.train_model():
            return np.array([]), [], None

        if self.base_date is None:
            return np.array([]), [], None

        future_days = np.arange(0, 365 * 5 + 1, 7)  # 5-year forecast, weekly resolution.
        x_future = future_days.reshape(-1, 1)
        y_pred = self.model.predict(x_future)
        future_dates = [self.base_date + timedelta(days=int(d)) for d in future_days]

        end_life_date = None
        below_threshold = np.where(y_pred <= self.end_life_threshold)[0]
        if len(below_threshold) > 0:
            end_life_date = future_dates[int(below_threshold[0])]

        return y_pred, future_dates, end_life_date

    def _model_quality_text(self) -> str:
        if self.model is None or self.df is None or self.base_date is None:
            return "Model quality not available."

        x = ((self.df["date"] - self.base_date).dt.total_seconds() / 86400.0).to_numpy().reshape(-1, 1)
        y = self.df["capacity_percent"].to_numpy()
        r2 = float(self.model.score(x, y))
        slope = float(self.model.coef_[0])

        return (
            f"Model: Theil-Sen robust linear regression | R^2={r2:.3f} | "
            f"Estimated degradation rate={slope:.4f} %/day"
        )

    def plot_and_predict(self) -> None:
        """Render timeline and forecast; display end-of-life estimate and model metrics."""
        if self.df is None:
            messagebox.showerror("Data Error", "No data loaded. Load a CSV, capture data, or generate sample data.")
            return

        if not self.train_model():
            return

        y_pred, future_dates, end_life_date = self.predict_future()

        self.ax.clear()
        self.ax.plot(
            self.df["date"],
            self.df["capacity_percent"],
            "o-",
            color="#1f77b4",
            markersize=4,
            label="Historical samples",
        )

        if len(y_pred) > 0:
            self.ax.plot(
                future_dates,
                y_pred,
                "--",
                color="#d62728",
                linewidth=2,
                label="Theil-Sen forecast",
            )

        self.ax.axhline(
            y=self.end_life_threshold,
            color="#2ca02c",
            linestyle=":",
            label=f"End-of-life threshold ({self.end_life_threshold:.0f}%)",
        )

        if end_life_date is not None and len(y_pred) > 0:
            idx = next((i for i, dt in enumerate(future_dates) if dt >= end_life_date), None)
            if idx is not None:
                self.ax.axvline(
                    x=end_life_date,
                    color="#ff7f0e",
                    linestyle="--",
                    label=f"Predicted end-of-life: {end_life_date.strftime('%Y-%m-%d')}",
                )
                self.ax.plot(end_life_date, y_pred[idx], "o", color="#ff7f0e", markersize=7)

        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("Battery Health (%)")
        self.ax.set_title("Battery Degradation Trend and Lifetime Forecast")
        self.ax.grid(True, linestyle=":", alpha=0.6)
        self.ax.legend(loc="best")

        self.figure.autofmt_xdate()
        self.canvas.draw()

        current_capacity = float(self.df["capacity_percent"].iloc[-1])
        model_quality = self._model_quality_text()

        if end_life_date is not None:
            days_left = (end_life_date - datetime.now()).days
            if days_left <= 0:
                summary = (
                    f"Current capacity: {current_capacity:.1f}%\n"
                    f"Status: The forecast indicates the battery is already at or below {self.end_life_threshold:.0f}%.\n"
                    f"Recommendation: Plan battery replacement."
                )
            else:
                summary = (
                    f"Current capacity: {current_capacity:.1f}%\n"
                    f"Predicted end-of-life date (<= {self.end_life_threshold:.0f}%): {end_life_date.strftime('%Y-%m-%d')}\n"
                    f"Estimated remaining time: ~{days_left} days"
                )
        else:
            summary = (
                f"Current capacity: {current_capacity:.1f}%\n"
                f"The forecast does not cross {self.end_life_threshold:.0f}% within the 5-year horizon."
            )

        self.result_label.config(text=f"{summary}\n{model_quality}")
        status_end_life = end_life_date.strftime("%Y-%m-%d") if end_life_date else "not reached in horizon"
        self.status_label.config(text=f"Analysis complete. Predicted end-of-life: {status_end_life}.")


if __name__ == "__main__":
    root = tk.Tk()
    app = BatteryAnalyzer(root)
    root.mainloop()
