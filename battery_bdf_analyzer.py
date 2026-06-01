#!/usr/bin/env python3
"""
Tkinter-based Battery Data Format (BDF) analyzer.

The application loads BDF-compatible CSV files, normalizes official preferred
labels and known aliases, computes SOH, trains linear/SVR models, visualizes
results, and estimates remaining useful life (RUL).
"""

import sys
import signal
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR


class BatteryBDFAnalyzer:
    """Interactive GUI analyzer for BDF time-series battery datasets."""

    def __init__(self):
        """Initialize models, GUI state, and the main window."""
        self.data = pd.DataFrame()
        self.linear_model = None
        self.svr_model = None
        self.scaler = StandardScaler()
        self._closing = False

        self.root = tk.Tk()
        self.root.title("Battery BDF Analyzer")
        self.root.geometry("1200x800")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._setup_gui()

    def _on_close(self) -> None:
        """Close app resources and terminate the Tk loop safely."""
        if self._closing:
            return
        self._closing = True
        try:
            plt.close("all")
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def _setup_signal_handlers(self) -> None:
        """Handle Ctrl+C (SIGINT) gracefully while Tk mainloop is running."""

        def _handle_sigint(_sig, _frame):
            self._on_close()

        signal.signal(signal.SIGINT, _handle_sigint)
        self._keep_alive_for_signals()

    def _keep_alive_for_signals(self) -> None:
        """Periodic no-op callback so Python keeps processing signal checks."""
        if not self._closing:
            self.root.after(200, self._keep_alive_for_signals)

    def load_bdf(self, filepath: str) -> None:
        """Load and normalize a BDF CSV file."""
        try:
            df = pd.read_csv(filepath)
            df = self._normalize_columns(df)
            required = ["test_time_second", "voltage_volt", "current_ampere"]
            missing = [col for col in required if col not in df.columns]
            if missing:
                raise ValueError(f"Missing BDF columns: {missing}")

            for col in ["unix_time_second", "cycle_count", "capacity_percent", "power_watt", "temperature_celsius"]:
                if col not in df.columns:
                    df[col] = np.nan

            if "temperature_celsius" not in df.columns and "ambient_temperature_celsius" in df.columns:
                df["temperature_celsius"] = df["ambient_temperature_celsius"]

            if "unix_time_second" in df.columns and df["unix_time_second"].notna().any():
                df["timestamp"] = pd.to_datetime(df["unix_time_second"], unit="s", errors="coerce")
            else:
                start = datetime.now()
                df["timestamp"] = start + pd.to_timedelta(df["test_time_second"], unit="s")

            self.data = df.sort_values("test_time_second").reset_index(drop=True)
            self._update_gui_after_load()
            self.status.config(text=f"Loaded {Path(filepath).name}")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load BDF file: {exc}")

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize preferred-label and legacy headers to internal aliases."""
        column_map = {
            "Test Time / s": "test_time_second",
            "Voltage / V": "voltage_volt",
            "Current / A": "current_ampere",
            "Cycle Count / 1": "cycle_count",
            "Power / W": "power_watt",
            "Ambient Temperature / degC": "ambient_temperature_celsius",
            "Capacity / %": "capacity_percent",
            "Temperature / degC": "temperature_celsius",
            "Temperature / °C": "temperature_celsius",
            "Unix Time / s": "unix_time_second",
            "Step Capacity / Ah": "step_capacity_ah",
            "Step Energy / Wh": "step_energy_wh",
            "Step Index / 1": "step_index",
        }

        available_map = {src: dst for src, dst in column_map.items() if src in df.columns}
        if available_map:
            df = df.rename(columns=available_map)

        return df

    def compute_soh(self) -> np.ndarray | None:
        """Compute SOH values, using measured capacity when available."""
        if self.data.empty:
            return None

        if "capacity_percent" in self.data.columns and self.data["capacity_percent"].notna().any():
            return pd.to_numeric(self.data["capacity_percent"], errors="coerce").ffill().fillna(100.0).values

        times = pd.to_numeric(self.data["test_time_second"], errors="coerce").fillna(0.0).values
        currents = pd.to_numeric(self.data["current_ampere"], errors="coerce").fillna(0.0).values

        dt = np.diff(times, prepend=times[0])
        dt = np.clip(dt, 0.0, None)
        ah_throughput = np.cumsum(np.abs(currents) * dt) / 3600.0

        max_ah = float(np.max(ah_throughput)) if len(ah_throughput) else 0.0
        if max_ah <= 0:
            return np.full(len(self.data), 100.0)

        soh = (max_ah - ah_throughput) / max_ah * 100.0
        return np.clip(soh, 0.0, 100.0)

    def fit_linear(self) -> dict | None:
        """Fit linear SOH degradation model versus test time."""
        if self.data.empty:
            return None

        soh = self.compute_soh()
        if soh is None or len(soh) < 2:
            return None

        x = self.data["test_time_second"].values.reshape(-1, 1)
        model = LinearRegression()
        model.fit(x, soh)
        y_pred = model.predict(x)

        self.linear_model = model
        return {
            "r2": r2_score(soh, y_pred),
            "coef": float(model.coef_[0]),
            "intercept": float(model.intercept_),
        }

    def predict_rul_linear(self, eol_soh: float = 70.0) -> float | None:
        """Estimate remaining seconds to reach the specified EOL threshold."""
        if self.linear_model is None or self.data.empty:
            return None

        soh = self.compute_soh()
        if soh is None or len(soh) == 0:
            return None

        current_soh = float(soh[-1])
        if current_soh <= eol_soh:
            return 0.0

        slope = float(self.linear_model.coef_[0])
        intercept = float(self.linear_model.intercept_)

        if slope >= 0:
            return float("inf")

        t_eol = (eol_soh - intercept) / slope
        current_t = float(self.data["test_time_second"].iloc[-1])
        return max(0.0, t_eol - current_t)

    def fit_svr(self, kernel: str = "rbf", c_value: float = 10.0, epsilon: float = 0.01) -> dict | None:
        """Train an SVR SOH model from time, voltage, current, and temperature."""
        if self.data.empty:
            return None

        soh = self.compute_soh()
        if soh is None or len(soh) < 2:
            return None

        features = self._get_svr_features()
        x_scaled = self.scaler.fit_transform(features)

        model = SVR(kernel=kernel, C=c_value, epsilon=epsilon)
        model.fit(x_scaled, soh)
        y_pred = model.predict(x_scaled)

        self.svr_model = model
        return {
            "r2": r2_score(soh, y_pred),
            "mae": mean_absolute_error(soh, y_pred),
        }

    def predict_future_svr(self, future_seconds: float) -> tuple[np.ndarray, np.ndarray] | tuple[None, None]:
        """Forecast future SOH over a fixed horizon using the trained SVR model."""
        if self.svr_model is None or self.data.empty:
            return None, None

        last_time = float(self.data["test_time_second"].iloc[-1])
        future_times = np.linspace(last_time, last_time + future_seconds, num=100)

        last_row = self.data.iloc[-1]
        x_future = pd.DataFrame(
            {
                "test_time_second": future_times,
                "voltage_volt": float(last_row["voltage_volt"]),
                "current_ampere": float(last_row["current_ampere"]),
                "temperature_celsius": float(last_row.get("temperature_celsius", 25.0)),
            }
        )

        x_future_scaled = self.scaler.transform(x_future)
        y_future = self.svr_model.predict(x_future_scaled)
        return future_times, y_future

    def _setup_gui(self) -> None:
        """Create menus, tabs, plots, and status bar."""
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open BDF File", command=self._open_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_overview = ttk.Frame(notebook)
        self.tab_linear = ttk.Frame(notebook)
        self.tab_svr = ttk.Frame(notebook)

        notebook.add(self.tab_overview, text="Dashboard")
        notebook.add(self.tab_linear, text="Linear Model")
        notebook.add(self.tab_svr, text="SVR Model")

        self._build_overview_tab()
        self._build_linear_tab()
        self._build_svr_tab()

        self.status = tk.Label(self.root, text="Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_overview_tab(self) -> None:
        """Create overview plot and summary text area."""
        self.fig_overview, self.ax_overview = plt.subplots(figsize=(7, 4))
        self.canvas_overview = FigureCanvasTkAgg(self.fig_overview, master=self.tab_overview)
        self.canvas_overview.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.info_label = tk.Label(self.tab_overview, text="No data loaded.", justify=tk.LEFT)
        self.info_label.pack(pady=10)

    def _build_linear_tab(self) -> None:
        """Create linear model controls, plot, and RUL label."""
        control = ttk.Frame(self.tab_linear)
        control.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control, text="End-of-Life SOH threshold (%):").pack(side=tk.LEFT)
        self.eol_var = tk.StringVar(value="70")
        ttk.Entry(control, textvariable=self.eol_var, width=6).pack(side=tk.LEFT, padx=6)
        ttk.Button(control, text="Calculate RUL", command=self._update_linear).pack(side=tk.LEFT, padx=10)

        self.linear_fig, self.linear_ax = plt.subplots(figsize=(7, 4))
        self.linear_canvas = FigureCanvasTkAgg(self.linear_fig, master=self.tab_linear)
        self.linear_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.rul_label = tk.Label(self.tab_linear, text="RUL: Not computed", font=("Arial", 12))
        self.rul_label.pack(pady=10)

    def _build_svr_tab(self) -> None:
        """Create SVR training/prediction controls, plot, and metrics label."""
        control = ttk.Frame(self.tab_svr)
        control.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(control, text="Train SVR", command=self._train_svr).pack(side=tk.LEFT, padx=5)
        ttk.Label(control, text="Predict future (days):").pack(side=tk.LEFT, padx=10)
        self.svr_days_var = tk.StringVar(value="30")
        ttk.Entry(control, textvariable=self.svr_days_var, width=6).pack(side=tk.LEFT, padx=6)
        ttk.Button(control, text="Predict", command=self._predict_svr).pack(side=tk.LEFT, padx=5)

        self.svr_fig, self.svr_ax = plt.subplots(figsize=(7, 4))
        self.svr_canvas = FigureCanvasTkAgg(self.svr_fig, master=self.tab_svr)
        self.svr_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.svr_metrics_label = tk.Label(self.tab_svr, text="SVR not trained.", justify=tk.LEFT)
        self.svr_metrics_label.pack(pady=10)

    def _update_gui_after_load(self) -> None:
        """Refresh all charts, metrics, and labels after loading new data."""
        self._plot_soh_overview()
        self._update_linear()
        self._train_svr()

        if self.data.empty:
            self.info_label.config(text="No data loaded.")
            return

        soh = self.compute_soh()
        current_soh = float(soh[-1]) if soh is not None and len(soh) else np.nan
        start = float(self.data["test_time_second"].min())
        end = float(self.data["test_time_second"].max())

        lines = [
            f"BDF file loaded: {len(self.data)} samples",
            f"Time range: {start:.1f} to {end:.1f} s",
            f"Current SOH: {current_soh:.1f}%",
        ]
        self.info_label.config(text="\n".join(lines))

    def _plot_soh_overview(self) -> None:
        """Plot SOH history in the dashboard tab."""
        self.ax_overview.clear()

        if self.data.empty:
            self.ax_overview.text(0.5, 0.5, "No data", transform=self.ax_overview.transAxes, ha="center")
            self.canvas_overview.draw()
            return

        soh = self.compute_soh()
        if soh is None:
            self.canvas_overview.draw()
            return

        time_sec = self.data["test_time_second"].values
        self.ax_overview.plot(time_sec, soh, "b-", label="SOH (estimated)")
        self.ax_overview.axhline(y=70, color="r", linestyle="--", label="EOL (70%)")
        self.ax_overview.set_xlabel("Time (s)")
        self.ax_overview.set_ylabel("State of Health (%)")
        self.ax_overview.set_title("Battery Health Over Time")
        self.ax_overview.legend()
        self.ax_overview.grid(True, alpha=0.3)
        self.canvas_overview.draw()

    def _update_linear(self) -> None:
        """Update linear fit chart and RUL label from current dataset."""
        if self.data.empty:
            self.rul_label.config(text="Linear model failed. Need data.")
            return

        metrics = self.fit_linear()
        if not metrics:
            self.rul_label.config(text="Linear model failed. Need more data.")
            return

        soh = self.compute_soh()
        time_sec = self.data["test_time_second"].values
        pred = self.linear_model.predict(time_sec.reshape(-1, 1))

        self.linear_ax.clear()
        self.linear_ax.plot(time_sec, soh, "bo", markersize=3, label="Observed SOH")
        self.linear_ax.plot(time_sec, pred, "r-", label=f"Linear Fit (R²={metrics['r2']:.3f})")
        self.linear_ax.axhline(y=70, color="g", linestyle="--", label="EOL threshold")
        self.linear_ax.set_xlabel("Time (s)")
        self.linear_ax.set_ylabel("SOH (%)")
        self.linear_ax.legend()
        self.linear_ax.grid(True, alpha=0.3)
        self.linear_canvas.draw()

        try:
            eol = float(self.eol_var.get())
        except Exception:
            eol = 70.0

        remaining = self.predict_rul_linear(eol)
        if remaining is None:
            self.rul_label.config(text="Linear RUL: unavailable")
        elif remaining == float("inf"):
            self.rul_label.config(text="Linear RUL: ∞ (no degradation or improving)")
        else:
            days = remaining / 86400.0
            hours = remaining / 3600.0
            self.rul_label.config(text=f"Linear RUL: {days:.2f} days ({hours:.1f} hours) until SOH={eol:.0f}%")

    def _train_svr(self) -> None:
        """Train SVR and redraw observed-versus-predicted SOH chart."""
        if self.data.empty:
            self.svr_metrics_label.config(text="No data loaded.")
            return

        metrics = self.fit_svr()
        if not metrics:
            self.svr_metrics_label.config(text="SVR training failed. Check data.")
            return

        x_scaled = self.scaler.transform(self._get_svr_features())
        y_pred = self.svr_model.predict(x_scaled)
        soh = self.compute_soh()

        self.svr_ax.clear()
        self.svr_ax.plot(self.data["test_time_second"].values, soh, "bo", markersize=3, label="True SOH")
        self.svr_ax.plot(self.data["test_time_second"].values, y_pred, "r-", label="SVR Prediction")
        self.svr_ax.legend()
        self.svr_ax.grid(True, alpha=0.3)
        self.svr_canvas.draw()

        self.svr_metrics_label.config(text=f"SVR trained: R²={metrics['r2']:.3f}, MAE={metrics['mae']:.2f}%")

    def _predict_svr(self) -> None:
        """Project future SOH with SVR and display EOL-related message."""
        if self.svr_model is None:
            messagebox.showwarning("Warning", "Train SVR first.")
            return

        try:
            days = float(self.svr_days_var.get())
        except Exception:
            days = 30.0

        future_seconds = days * 86400.0
        times, soh_pred = self.predict_future_svr(future_seconds)
        if times is None:
            return

        soh = self.compute_soh()

        self.svr_ax.clear()
        self.svr_ax.plot(self.data["test_time_second"].values, soh, "bo", markersize=3, label="Historical")
        self.svr_ax.plot(times, soh_pred, "r--", label=f"SVR Prediction ({days:.0f} days)")
        self.svr_ax.axhline(y=70, color="g", linestyle="--", label="EOL")
        self.svr_ax.legend()
        self.svr_ax.grid(True, alpha=0.3)
        self.svr_canvas.draw()

        below = pd.Series(soh_pred, index=times)
        eol_idx = below[below <= 70].index
        if len(eol_idx) > 0:
            t_eol = float(eol_idx[0])
            remaining_days = (t_eol - float(self.data["test_time_second"].iloc[-1])) / 86400.0
            msg = f"SVR predicts EOL in {remaining_days:.1f} days (SOH=70%)"
        else:
            msg = f"SVR predicts SOH > 70% for next {days:.0f} days"

        r2_now = self.svr_model.score(self.scaler.transform(self._get_svr_features()), soh)
        self.svr_metrics_label.config(text=f"{msg}\nR²={r2_now:.3f}")

    def _get_svr_features(self) -> pd.DataFrame:
        """Build feature matrix for SVR from current data."""
        features = self.data[["test_time_second", "voltage_volt", "current_ampere"]].copy()
        if "temperature_celsius" in self.data.columns:
            features["temperature_celsius"] = pd.to_numeric(self.data["temperature_celsius"], errors="coerce").fillna(25.0)
        else:
            features["temperature_celsius"] = 25.0
        return features

    def _open_file(self) -> None:
        """Open file picker for BDF CSV files."""
        filepath = filedialog.askopenfilename(filetypes=[("BDF CSV", "*.csv"), ("All files", "*.*")])
        if filepath:
            self.load_bdf(filepath)

    def run(self) -> None:
        """Start the Tk event loop with graceful signal handling."""
        self._setup_signal_handlers()
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self._on_close()


def main(argv: list[str]) -> int:
    """Application entry point with optional initial BDF file argument."""
    try:
        app = BatteryBDFAnalyzer()
        if len(argv) > 1:
            app.load_bdf(argv[1])
        else:
            default_file = Path(__file__).resolve().parent / "battery_data.bdf.csv"
            if default_file.exists():
                app.load_bdf(str(default_file))
        app.run()
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
