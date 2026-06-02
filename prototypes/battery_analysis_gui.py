#!/usr/bin/env python3
"""Graphical user interface for battery health monitoring and analysis.

This application provides a real-time dashboard and historical analysis view
for laptop batteries on Linux. It combines live sysfs collection with the
estimation logic from the rest of the battery-health-analyzer project.

Main features:
- Live monitoring of battery metrics (SOH, capacity, voltage, current, cycles).
- Circular gauge widgets for SOH and current charge.
- Three embedded matplotlib charts: SOH trend, degradation prediction, and
  SOH distribution.
- Remaining useful life (RUL) estimates displayed in the sidebar.
- Load and analyze historical CSV / JSON files.
- Export a plain-text report to disk.

Requirements:
    pip install numpy scipy pandas matplotlib
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import threading
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
import json
import pandas as pd
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import warnings
warnings.filterwarnings('ignore')

# Importa as classes dos scripts anteriores
import sys
from typing import Dict, Optional, List

# Configura matplotlib para usar backend TkAgg
plt.switch_backend('TkAgg')

class BatteryDataCollector:
    """Collect battery metrics from the Linux sysfs power interface."""

    def __init__(self, battery_path: str = "/sys/class/power_supply/BAT0"):
        self.battery_path = Path(battery_path)
        self.valid = self._check_battery_exists()
    
    def _check_battery_exists(self) -> bool:
        """Return True if a battery device is found, with auto-discovery fallback."""
        if not self.battery_path.exists():
            power_supply_path = Path("/sys/class/power_supply/")
            batteries = [p for p in power_supply_path.iterdir() 
                        if (p / "type").exists() and 
                        (p / "type").read_text().strip() == "Battery"]
            if batteries:
                self.battery_path = batteries[0]
                return True
            return False
        return True
    
    def _read_sysfs_file(self, filename: str, convert_to_float: bool = True):
        """Read a sysfs file, converting micro-unit values to base units when needed."""
        filepath = self.battery_path / filename
        if not filepath.exists():
            return None
        try:
            content = filepath.read_text().strip()
            if convert_to_float:
                return float(content) / 1000000.0 if 'now' in filename or 'full' in filename else float(content)
            return content
        except (ValueError, IOError):
            return None
    
    def get_battery_info(self) -> Dict:
        """Collect a snapshot of available battery metrics and return as a dict."""
        info = {
            'timestamp': datetime.now().isoformat(),
            'unix_timestamp': time.time(),
        }
        
        files_to_read = {
            'energy_now': 'current_energy_wh',
            'energy_full': 'current_full_energy_wh',
            'energy_full_design': 'design_energy_wh',
            'voltage_now': 'current_voltage_v',
            'current_now': 'current_a',
            'cycle_count': 'cycle_count',
            'capacity': 'capacity_percent',
            'status': 'status',
            'health': 'health',
        }
        
        for sysfs_file, friendly_name in files_to_read.items():
            if sysfs_file in ['status', 'health']:
                value = self._read_sysfs_file(sysfs_file, convert_to_float=False)
            else:
                value = self._read_sysfs_file(sysfs_file, convert_to_float=True)
            if value is not None:
                info[friendly_name] = value
        
        if 'design_energy_wh' in info and 'current_full_energy_wh' in info:
            soh = (info['current_full_energy_wh'] / info['design_energy_wh']) * 100
            info['soh_percent'] = round(soh, 2)
        
        return info


class BatteryEstimator:
    """Estimate battery health metrics from historical data.

    Accepts either a file path or an in-memory DataFrame produced by
    `BatteryDataCollector` during live monitoring.
    """

    def __init__(self, data_file: str = None, data_df: pd.DataFrame = None):
        if data_file:
            self.data = self._load_data(data_file)
        elif data_df is not None:
            self.data = data_df
        else:
            self.data = pd.DataFrame()
    
    def _load_data(self, data_file: str):
        """Load battery data from a CSV or JSON file."""
        path = Path(data_file)
        if path.suffix == '.csv':
            df = pd.read_csv(path)
        elif path.suffix == '.json':
            with open(path, 'r', encoding='utf-8') as file:
                raw = json.load(file)
            df = pd.DataFrame(raw) if isinstance(raw, list) else pd.DataFrame([raw])
        else:
            raise ValueError(f"Unsupported format: {path.suffix}")

        # Normalize alternative collector schemas (e.g., *.bdf.csv) to internal names.
        if 'timestamp' not in df.columns:
            if 'unix_time_second' in df.columns:
                df['timestamp'] = pd.to_datetime(df['unix_time_second'], unit='s', errors='coerce')
            elif 'test_time_second' in df.columns:
                df['timestamp'] = pd.to_datetime(df['test_time_second'], unit='s', errors='coerce')

        if 'soh_percent' not in df.columns:
            if 'capacity_percent' in df.columns:
                df['soh_percent'] = pd.to_numeric(df['capacity_percent'], errors='coerce')

        if 'current_voltage_v' not in df.columns and 'voltage_volt' in df.columns:
            df['current_voltage_v'] = pd.to_numeric(df['voltage_volt'], errors='coerce')

        if 'current_a' not in df.columns and 'current_ampere' in df.columns:
            df['current_a'] = pd.to_numeric(df['current_ampere'], errors='coerce')

        if 'cycle_count' not in df.columns and 'cycle_count' in df.columns:
            df['cycle_count'] = pd.to_numeric(df['cycle_count'], errors='coerce')

        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    def calculate_current_soh(self):
        """Return the SOH of the most recent data point, or None."""
        if self.data.empty:
            return None
        latest = self.data.iloc[-1]
        if 'soh_percent' in latest and pd.notna(latest['soh_percent']):
            return float(latest['soh_percent'])
        elif 'soh_percentual' in latest and pd.notna(latest['soh_percentual']):
            return float(latest['soh_percentual'])
        elif 'current_full_energy_wh' in latest and 'design_energy_wh' in latest:
            return (latest['current_full_energy_wh'] / latest['design_energy_wh']) * 100
        elif 'energia_total_atual_wh' in latest and 'energia_design_wh' in latest:
            return (latest['energia_total_atual_wh'] / latest['energia_design_wh']) * 100
        return None
    
    def estimate_degradation_rate(self):
        """Fit a linear model to SOH over time and return daily/monthly/yearly rates."""
        if self.data.empty:
            return None
        
        soh_data = []
        time_data = []
        
        for idx, row in self.data.iterrows():
            soh = None
            if 'soh_percent' in row and pd.notna(row['soh_percent']):
                soh = float(row['soh_percent'])
            elif 'soh_percentual' in row and pd.notna(row['soh_percentual']):
                soh = float(row['soh_percentual'])
            elif 'current_full_energy_wh' in row and 'design_energy_wh' in row:
                soh = (row['current_full_energy_wh'] / row['design_energy_wh']) * 100
            elif 'energia_total_atual_wh' in row and 'energia_design_wh' in row:
                soh = (row['energia_total_atual_wh'] / row['energia_design_wh']) * 100
            
            if soh is not None and soh > 0:
                soh_data.append(soh)
                if 'timestamp' in row and pd.notna(row['timestamp']):
                    if len(time_data) == 0:
                        start_time = row['timestamp']
                    days = (row['timestamp'] - start_time).total_seconds() / 86400.0
                    time_data.append(days)
                else:
                    time_data.append(float(idx))
        
        if len(soh_data) < 3:
            return None
        
        time_data = np.array(time_data, dtype=float)
        soh_data = np.array(soh_data)

        if time_data[-1] - time_data[0] == 0:
            return None

        try:
            linear_coef = np.polyfit(time_data, soh_data, 1)
        except np.linalg.LinAlgError:
            return None
        linear_rate = linear_coef[0]
        
        return {
            'rate_daily': linear_rate,
            'rate_monthly': linear_rate * 30,
            'rate_yearly': linear_rate * 365,
            'intercept': linear_coef[1],
            'data_points': len(soh_data)
        }
    
    def estimate_remaining_useful_life(self, eol_threshold: float = 70):
        """Estimate remaining useful life in days/months/years from the linear model."""
        current_soh = self.calculate_current_soh()
        if current_soh is None:
            return None
        
        degradation = self.estimate_degradation_rate()
        if degradation is None or degradation['rate_daily'] >= 0:
            return None
        
        rate = degradation['rate_daily']
        MAX_DAYS = 36500  # Cap at 100 years to avoid overflow.
        days_to_eol = (eol_threshold - current_soh) / rate if rate < 0 else float('inf')
        days_display = min(days_to_eol, MAX_DAYS) if days_to_eol != float('inf') else MAX_DAYS
        
        return {
            'current_soh': current_soh,
            'days_remaining': days_to_eol,
            'months_remaining': days_display / 30,
            'years_remaining': days_display / 365,
            'rate_daily': rate,
            'rate_yearly': rate * 365
        }
    
    def predict_future_soh(self, days_ahead: int = 365):
        """Return arrays of future days and predicted SOH values."""
        degradation = self.estimate_degradation_rate()
        current_soh = self.calculate_current_soh()
        if degradation is None or current_soh is None:
            return None
        
        future_days = np.arange(0, days_ahead + 1)
        predicted_soh = current_soh + (degradation['rate_daily'] * future_days)
        predicted_soh = np.maximum(predicted_soh, 0)
        
        return {'days': future_days, 'soh': predicted_soh}
    
    def get_soh_history(self):
        """Return parallel lists of timestamps and SOH values from the dataset."""
        if self.data.empty:
            return [], []
        
        timestamps = []
        soh_values = []
        
        for idx, row in self.data.iterrows():
            soh = None
            if 'soh_percent' in row and pd.notna(row['soh_percent']):
                soh = float(row['soh_percent'])
            elif 'soh_percentual' in row and pd.notna(row['soh_percentual']):
                soh = float(row['soh_percentual'])
            elif 'current_full_energy_wh' in row and 'design_energy_wh' in row:
                soh = (row['current_full_energy_wh'] / row['design_energy_wh']) * 100
            elif 'energia_total_atual_wh' in row and 'energia_design_wh' in row:
                soh = (row['energia_total_atual_wh'] / row['energia_design_wh']) * 100
            
            if soh is not None and 'timestamp' in row and pd.notna(row['timestamp']):
                timestamps.append(row['timestamp'])
                soh_values.append(soh)
        
        return timestamps, soh_values


class BatteryMonitorApp:
    """Main Tk application window for battery health monitoring."""

    def __init__(self, root):
        self.root = root
        self.root.title("Battery Health Monitor")
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')
        
        # Variáveis
        self.data_file = None
        self.collector = None
        self.estimator = None
        self.live_mode = False
        self.live_thread = None
        self.live_data = []  # Armazena dados ao vivo
        
        # Cores
        self.colors = {
            'bg': '#f0f0f0',
            'primary': '#2c3e50',
            'success': '#27ae60',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'info': '#3498db'
        }
        
        self._setup_ui()
        self._check_battery_hardware()
        
    def _setup_ui(self):
        """Build and arrange all UI widgets."""
        # Frame principal
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Barra de ferramentas superior
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(toolbar, text="Open File", command=self.load_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Start Live Monitoring", command=self.start_live_monitoring).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Stop Monitoring", command=self.stop_live_monitoring).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Export Report", command=self.export_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_display).pack(side=tk.LEFT, padx=5)
        
        self.status_label = ttk.Label(toolbar, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)
        
        # Frame de conteúdo (dividido em 3 colunas)
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left column — main battery metrics.
        left_frame = ttk.LabelFrame(content_frame, text="Battery Metrics", padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Indicadores circulares (canvas)
        self.canvas_frame = ttk.Frame(left_frame)
        self.canvas_frame.pack(fill=tk.X, pady=10)
        
        self.soh_meter = self._create_meter(self.canvas_frame, "Health (SOH)", 200, 200)
        self.soh_meter.pack(side=tk.LEFT, padx=10)
        
        self.cap_meter = self._create_meter(self.canvas_frame, "Current Charge", 200, 200)
        self.cap_meter.pack(side=tk.RIGHT, padx=10)
        
        # Métricas numéricas
        metrics_frame = ttk.Frame(left_frame)
        metrics_frame.pack(fill=tk.X, pady=10)
        
        self.metrics_labels = {}
        metrics = [
            ("Cycles:", "cycle_count", "0"),
            ("Voltage:", "voltage", "0 V"),
            ("Current:", "current", "0 A"),
            ("Power:", "power", "0 W"),
            ("Temperature:", "temp", "N/A"),
            ("Status:", "status", "Unknown"),
        ]
        
        for i, (label, key, default) in enumerate(metrics):
            frame = ttk.Frame(metrics_frame)
            frame.pack(fill=tk.X, pady=5)
            ttk.Label(frame, text=label, font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
            self.metrics_labels[key] = ttk.Label(frame, text=default, font=('Arial', 10))
            self.metrics_labels[key].pack(side=tk.RIGHT)
        
        # Center column — matplotlib charts.
        center_frame = ttk.LabelFrame(content_frame, text="Graphical Analysis", padding=10)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # Figura matplotlib
        self.fig = Figure(figsize=(6, 8), dpi=100)
        self.fig.patch.set_facecolor('#f0f0f0')
        
        # Subplots
        self.ax1 = self.fig.add_subplot(311)  # Evolução SOH
        self.ax2 = self.fig.add_subplot(312)  # Predição
        self.ax3 = self.fig.add_subplot(313)  # Distribuição
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=center_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Barra de navegação do matplotlib
        toolbar_frame = ttk.Frame(center_frame)
        toolbar_frame.pack(fill=tk.X)
        NavigationToolbar2Tk(self.canvas, toolbar_frame)
        
        # Right column — report and RUL estimates.
        right_frame = ttk.LabelFrame(content_frame, text="Report & Log", padding=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Texto do relatório
        self.report_text = ScrolledText(right_frame, height=15, width=40, wrap=tk.WORD)
        self.report_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Estimativas de vida útil
        self.rul_frame = ttk.LabelFrame(right_frame, text="Remaining Useful Life", padding=10)
        self.rul_frame.pack(fill=tk.X)
        
        self.rul_labels = {}
        rul_metrics = [
            ("Days:", "days"),
            ("Months:", "months"),
            ("Years:", "years"),
            ("Degradation rate:", "rate"),
        ]
        
        for label, key in rul_metrics:
            frame = ttk.Frame(self.rul_frame)
            frame.pack(fill=tk.X, pady=2)
            ttk.Label(frame, text=label, font=('Arial', 9, 'bold')).pack(side=tk.LEFT)
            self.rul_labels[key] = ttk.Label(frame, text="--", font=('Arial', 9))
            self.rul_labels[key].pack(side=tk.RIGHT)
    
    def _create_meter(self, parent, title, width, height):
        """Create a semi-circular gauge widget using a Tk Canvas."""
        frame = ttk.Frame(parent)
        canvas = tk.Canvas(frame, width=width, height=height, bg='white', highlightthickness=0)
        canvas.pack()
        
        title_label = ttk.Label(frame, text=title, font=('Arial', 10, 'bold'))
        title_label.pack()
        
        value_label = ttk.Label(frame, text="0%", font=('Arial', 16, 'bold'))
        value_label.pack()
        
        # Armazena referências
        canvas.value_label = value_label
        canvas.title = title
        canvas.width = width
        canvas.height = height
        
        # Desenha o arco
        self._draw_meter_arc(canvas, 0)
        
        return frame
    
    def _draw_meter_arc(self, canvas, percentage):
        """Redraw the gauge arc for a new percentage value."""
        canvas.delete("arc")
        width = canvas.width
        height = canvas.height
        center_x, center_y = width // 2, height - 50
        radius = 70
        
        # Arc spans from -90° to +90° (180° total).
        start_angle = -90
        end_angle = -90 + (percentage / 100) * 180
        
        if percentage < 70:
            color = '#e74c3c'  # Red — critical.
        elif percentage < 85:
            color = '#f39c12'  # Orange — degraded.
        else:
            color = '#27ae60'  # Green — healthy.
        
        # Background track.
        canvas.create_arc(center_x - radius, center_y - radius,
                         center_x + radius, center_y + radius,
                         start=start_angle, extent=180,
                         fill='', outline='#e0e0e0', width=15,
                         style='arc', tags="arc")
        
        # Filled arc.
        canvas.create_arc(center_x - radius, center_y - radius,
                         center_x + radius, center_y + radius,
                         start=start_angle, extent=percentage * 1.8,
                         fill='', outline=color, width=15,
                         style='arc', tags="arc")
        
        # Atualiza texto
        canvas.value_label.config(text=f"{percentage:.1f}%")
    
    def _update_meter(self, meter_frame, value):
        """Update the gauge for the given meter frame with a new value."""
        for child in meter_frame.winfo_children():
            if isinstance(child, tk.Canvas):
                self._draw_meter_arc(child, value)
                break
    
    def _check_battery_hardware(self):
        """Detect battery hardware and update the status bar."""
        self.collector = BatteryDataCollector()
        if self.collector.valid:
            self.status_label.config(text="Battery hardware detected. Ready for monitoring.")
        else:
            self.status_label.config(text="No battery detected. Load a data file to analyze.")
    
    def load_file(self):
        """Open a file dialog to load a CSV or JSON dataset."""
        filename = filedialog.askopenfilename(
            title="Select data file",
            filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                self.data_file = filename
                self.estimator = BatteryEstimator(data_file=filename)
                self.refresh_display()
                self.status_label.config(text=f"File loaded: {Path(filename).name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file: {e}")
    
    def start_live_monitoring(self):
        """Start a background thread that collects live battery data."""
        if not self.collector or not self.collector.valid:
            messagebox.showwarning("Warning", "No battery detected on this system.")
            return
        
        if self.live_mode:
            return
        
        self.live_mode = True
        self.live_data = []
        self.live_thread = threading.Thread(target=self._live_monitoring_loop, daemon=True)
        self.live_thread.start()
        self.status_label.config(text="Live monitoring active...")
    
    def _live_monitoring_loop(self):
        """Background loop: collect a battery snapshot every 5 seconds."""
        while self.live_mode:
            try:
                data = self.collector.get_battery_info()
                self.live_data.append(data)
                
                # Keep at most 1000 points in memory.
                if len(self.live_data) > 1000:
                    self.live_data = self.live_data[-1000:]
                
                # Atualiza display na thread principal
                self.root.after(0, self._update_live_display, data)
                
                time.sleep(5)  # Coleta a cada 5 segundos
            except Exception as e:
                print(f"Error in live monitoring: {e}")
                time.sleep(5)
    
    def _update_live_display(self, data):
        """Rebuild the estimator from the current live buffer and refresh the UI."""
        # Converte dados para DataFrame
        df = pd.DataFrame(self.live_data)
        self.estimator = BatteryEstimator(data_df=df)
        self.refresh_display()
    
    def stop_live_monitoring(self):
        """Stop the live monitoring background thread."""
        self.live_mode = False
        self.status_label.config(text="Monitoring stopped")
    
    def refresh_display(self):
        """Refresh all widgets with the latest data from the current estimator."""
        if not self.estimator or self.estimator.data.empty:
            return
        
        # Atualiza SOH meter
        current_soh = self.estimator.calculate_current_soh()
        if current_soh:
            self._update_meter(self.soh_meter, current_soh)

        latest = self.estimator.data.iloc[-1]
        
        capacity_value = latest.get('capacity_percent', latest.get('capacidade_percentual', None))
        if pd.notna(capacity_value):
            self._update_meter(self.cap_meter, float(capacity_value))
        
        cycle_value = latest.get('cycle_count', latest.get('ciclos', None))
        if pd.notna(cycle_value):
            self.metrics_labels['cycle_count'].config(text=f"{float(cycle_value):.0f}")

        voltage = latest.get('current_voltage_v', latest.get('tensao_atual_v', None))
        if pd.notna(voltage):
            self.metrics_labels['voltage'].config(text=f"{voltage:.2f} V")

        current_a = latest.get('current_a', latest.get('corrente_atual_a', None))
        if pd.notna(current_a):
            self.metrics_labels['current'].config(text=f"{abs(current_a):.2f} A")
            if pd.notna(voltage):
                self.metrics_labels['power'].config(text=f"{abs(current_a) * voltage:.1f} W")

        if 'status' in latest and pd.notna(latest['status']):
            self.metrics_labels['status'].config(text=latest['status'])
        
        # Atualiza gráficos
        self._update_plots()
        
        # Atualiza relatório
        self._update_report()
        
        # Atualiza estimativas RUL
        self._update_rul_estimates()
    
    def _update_plots(self):
        """Refresh the three matplotlib charts with the current estimator data."""
        if not self.estimator or self.estimator.data.empty:
            return
        
        # Clear all axes.
        self.ax1.clear()
        self.ax2.clear()
        self.ax3.clear()
        
        # Chart 1: SOH history.
        timestamps, soh_values = self.estimator.get_soh_history()
        if timestamps and soh_values:
            self.ax1.plot(timestamps, soh_values, 'b-o', markersize=4, linewidth=1.5, label='Actual SOH')
            self.ax1.set_ylabel('SOH (%)')
            self.ax1.set_title('Battery Health Over Time')
            self.ax1.legend()
            self.ax1.grid(True, alpha=0.3)
            self.ax1.axhline(y=70, color='r', linestyle='--', linewidth=1, label='End-of-life (70%)')
            
            # Format x-axis as year-month.
            self.ax1.xaxis.set_major_formatter(DateFormatter('%Y-%m'))
            self.fig.autofmt_xdate()
        
        # Chart 2: Future prediction.
        current_soh = self.estimator.calculate_current_soh()
        future = self.estimator.predict_future_soh(days_ahead=365)
        if future is not None and current_soh:
            days = future['days']
            soh_pred = future['soh']
            
            self.ax2.plot(days, soh_pred, 'g--', linewidth=2, label='Linear prediction')
            self.ax2.axhline(y=70, color='r', linestyle=':', linewidth=1, label='EOL (70%)')
            self.ax2.set_xlabel('Days ahead')
            self.ax2.set_ylabel('SOH (%)')
            self.ax2.set_title('Degradation Forecast (Next 12 months)')
            self.ax2.legend()
            self.ax2.grid(True, alpha=0.3)
            
            # Highlight today.
            self.ax2.plot(0, current_soh, 'ro', markersize=8, label='Today')
        
        # Chart 3: SOH distribution histogram.
        if soh_values:
            self.ax3.hist(soh_values, bins=20, edgecolor='black', alpha=0.7, color='#3498db')
            self.ax3.axvline(x=np.mean(soh_values), color='r', linestyle='--', 
                           label=f'Mean: {np.mean(soh_values):.1f}%')
            self.ax3.axvline(x=soh_values[-1], color='g', linestyle='--',
                           label=f'Current: {soh_values[-1]:.1f}%')
            self.ax3.set_xlabel('SOH (%)')
            self.ax3.set_ylabel('Count')
            self.ax3.set_title('Historical SOH Distribution')
            self.ax3.legend()
            self.ax3.grid(True, alpha=0.3)
        
        self.fig.tight_layout()
        self.canvas.draw()
    
    def _update_report(self):
        """Rebuild the plain-text report in the Report tab."""
        if not self.estimator or self.estimator.data.empty:
            return
        
        report_lines = []
        report_lines.append("=" * 50)
        report_lines.append("BATTERY REPORT")
        report_lines.append("=" * 50)
        report_lines.append("")
        
        # Statistics.
        report_lines.append("📊 STATISTICS:")
        report_lines.append(f"   Total records: {len(self.estimator.data)}")
        
        timestamps, soh_values = self.estimator.get_soh_history()
        if timestamps:
            report_lines.append(f"   Period: {timestamps[0].strftime('%Y-%m-%d')} to {timestamps[-1].strftime('%Y-%m-%d')}")
            report_lines.append(f"   Initial SOH: {soh_values[0]:.1f}%")
            report_lines.append(f"   Current SOH: {soh_values[-1]:.1f}%")
            report_lines.append(f"   Total degradation: {soh_values[0] - soh_values[-1]:.1f}%")
        
        report_lines.append("")
        report_lines.append("🔋 CURRENT HEALTH:")
        current_soh = self.estimator.calculate_current_soh()
        if current_soh:
            report_lines.append(f"   SOH: {current_soh:.1f}%")
            if current_soh < 70:
                report_lines.append("   ⚠️  CRITICAL — Replacement required")
            elif current_soh < 80:
                report_lines.append("   ⚠️  WARNING — Significant degradation")
            elif current_soh < 90:
                report_lines.append("   ✓ Normal — Moderate degradation")
            else:
                report_lines.append("   ✓ Excellent — Battery is healthy")
        
        report_lines.append("")
        report_lines.append("📉 DEGRADATION RATE:")
        degradation = self.estimator.estimate_degradation_rate()
        if degradation:
            report_lines.append(f"   {degradation['rate_daily']:.3f}% per day")
            report_lines.append(f"   {degradation['rate_monthly']:.2f}% per month")
            report_lines.append(f"   {degradation['rate_yearly']:.2f}% per year")
        
        report_lines.append("")
        report_lines.append("=" * 50)
        
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, "\n".join(report_lines))
    
    def _update_rul_estimates(self):
        """Refresh the Remaining Useful Life labels in the right panel."""
        if not self.estimator or self.estimator.data.empty:
            return
        
        rul = self.estimator.estimate_remaining_useful_life()
        if rul:
            self.rul_labels['days'].config(text=f"{rul['days_remaining']:.0f} days")
            self.rul_labels['months'].config(text=f"{rul['months_remaining']:.1f} months")
            self.rul_labels['years'].config(text=f"{rul['years_remaining']:.2f} years")
            self.rul_labels['rate'].config(text=f"{rul['rate_yearly']:.2f}%/yr")
        else:
            for key in self.rul_labels:
                self.rul_labels[key].config(text="--")
    
    def export_report(self):
        """Save the current report text to a user-chosen file."""
        if not self.estimator or self.estimator.data.empty:
            messagebox.showwarning("Warning", "No data available to export.")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Save Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.report_text.get(1.0, tk.END))
                messagebox.showinfo("Success", f"Report saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {e}")


def main():
    """Launch the Battery Health Monitor application."""
    root = tk.Tk()
    app = BatteryMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()