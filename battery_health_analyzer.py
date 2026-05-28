#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ferramenta para análise e predição da vida útil da bateria no Linux (Ubuntu 24.04)
Utiliza dados históricos de capacidade da bateria e SVR para prever quando a
capacidade atingirá 80% (fim de vida útil recomendado).
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler
import os
import glob
from datetime import datetime, timedelta

class BatteryAnalyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("Analisador de Vida Útil da Bateria")
        self.root.geometry("900x700")
        
        # Dados
        self.df = None
        self.model = None
        self.scaler_x = StandardScaler()
        self.scaler_y = StandardScaler()
        
        # Limite de fim de vida (80% da capacidade original)
        self.end_life_threshold = 80.0
        
        # Frame principal
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Frame de botões
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="Carregar CSV Histórico", command=self.load_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Capturar Estado Atual", command=self.capture_current).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Gerar Dados de Exemplo", command=self.generate_sample).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Plotar e Prever", command=self.plot_and_predict).pack(side=tk.LEFT, padx=5)
        
        # Label de status
        self.status_label = ttk.Label(main_frame, text="Pronto. Carregue um arquivo CSV ou gere dados exemplo.", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(fill=tk.X, pady=5)
        
        # Frame para o gráfico
        self.figure = plt.Figure(figsize=(8, 5), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=main_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Frame para resultado da predição
        self.result_frame = ttk.LabelFrame(main_frame, text="Previsão de Vida Útil", padding="5")
        self.result_frame.pack(fill=tk.X, pady=5)
        
        self.result_label = ttk.Label(self.result_frame, text="Nenhuma previsão realizada ainda.", font=("Arial", 10))
        self.result_label.pack()
        
        # Inicializar informações do sistema
        self.current_battery_info()
    
    def current_battery_info(self):
        """Lê e exibe informações atuais da bateria no sistema (Ubuntu)."""
        try:
            # Procura por BAT0, BAT1, etc.
            battery_paths = glob.glob('/sys/class/power_supply/BAT*')
            if not battery_paths:
                self.status_label.config(text="Nenhuma bateria encontrada no sistema.")
                return
            
            bat_path = battery_paths[0]
            with open(os.path.join(bat_path, 'energy_full'), 'r') as f:
                energy_full = int(f.read().strip()) / 1000000  # µWh to Wh
            with open(os.path.join(bat_path, 'energy_full_design'), 'r') as f:
                energy_design = int(f.read().strip()) / 1000000
            
            capacity_pct = (energy_full / energy_design) * 100
            self.status_label.config(text=f"Bateria atual: {energy_full:.2f} Wh / {energy_design:.2f} Wh → {capacity_pct:.1f}% da capacidade original")
        except Exception as e:
            self.status_label.config(text=f"Erro ao ler bateria: {e}")
    
    def load_csv(self):
        """Carrega um arquivo CSV com colunas: data, capacidade_percent."""
        file_path = filedialog.askopenfilename(
            title="Selecione o arquivo CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            return
        
        try:
            df = pd.read_csv(file_path)
            # Verifica colunas necessárias
            required_cols = ['data', 'capacidade_percent']
            if not all(col in df.columns for col in required_cols):
                # Tenta detectar colunas case-insensitive
                df.columns = [col.lower() for col in df.columns]
                if not all(col in df.columns for col in required_cols):
                    raise ValueError("CSV deve conter colunas 'data' e 'capacidade_percent'")
            
            # Converte data para datetime
            df['data'] = pd.to_datetime(df['data'])
            df = df.sort_values('data')
            self.df = df[['data', 'capacidade_percent']].copy()
            self.status_label.config(text=f"Dados carregados: {len(self.df)} registros de {self.df['data'].min().date()} a {self.df['data'].max().date()}")
            messagebox.showinfo("Sucesso", f"Carregado {len(self.df)} registros.")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar CSV:\n{e}")
    
    def capture_current(self):
        """Adiciona o estado atual da bateria ao DataFrame (se existir) ou cria um novo."""
        try:
            battery_paths = glob.glob('/sys/class/power_supply/BAT*')
            if not battery_paths:
                messagebox.showerror("Erro", "Nenhuma bateria encontrada.")
                return
            
            bat_path = battery_paths[0]
            with open(os.path.join(bat_path, 'energy_full'), 'r') as f:
                energy_full = int(f.read().strip()) / 1000000
            with open(os.path.join(bat_path, 'energy_full_design'), 'r') as f:
                energy_design = int(f.read().strip()) / 1000000
            
            capacity_pct = (energy_full / energy_design) * 100
            current_date = datetime.now()
            
            new_record = pd.DataFrame({
                'data': [current_date],
                'capacidade_percent': [capacity_pct]
            })
            
            if self.df is None:
                self.df = new_record
                self.status_label.config(text=f"Novo histórico iniciado com valor atual: {capacity_pct:.1f}%")
            else:
                # Evitar duplicatas no mesmo dia
                last_date = self.df['data'].max()
                if (current_date - last_date).days < 1:
                    # Substitui o registro do mesmo dia
                    self.df = self.df[self.df['data'] < current_date]
                self.df = pd.concat([self.df, new_record], ignore_index=True)
                self.df = self.df.sort_values('data')
                self.status_label.config(text=f"Adicionado registro: {current_date.strftime('%Y-%m-%d')} -> {capacity_pct:.1f}%")
            
            messagebox.showinfo("Capturado", f"Capacidade atual: {capacity_pct:.1f}%\nAdicionado ao histórico.")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao capturar estado atual:\n{e}")
    
    def generate_sample(self):
        """Gera dados de exemplo simulando degradação realista de bateria."""
        # Simula 2 anos de dados com degradação não linear + ruído
        start_date = datetime.now() - timedelta(days=730)
        dates = [start_date + timedelta(days=i) for i in range(0, 730, 7)]  # semanal
        # Capacidade inicial 100%, decai exponencialmente até ~75% em 2 anos
        days = np.array([(d - start_date).days for d in dates])
        capacity = 100 * np.exp(-days / 1500)  # degradação suave
        # Adiciona ruído
        np.random.seed(42)
        noise = np.random.normal(0, 1.5, size=len(capacity))
        capacity = capacity + noise
        capacity = np.clip(capacity, 60, 100)
        
        self.df = pd.DataFrame({'data': dates, 'capacidade_percent': capacity})
        self.status_label.config(text=f"Dados de exemplo gerados: {len(self.df)} registros.")
        messagebox.showinfo("Exemplo", "Dados simulados gerados. Clique em 'Plotar e Prever'.")
    
    def train_svr(self):
        """Treina modelo SVR para predizer capacidade ao longo do tempo."""
        if self.df is None or len(self.df) < 4:
            messagebox.showerror("Erro", "Dados insuficientes para treinamento (mínimo 4 pontos).")
            return False
        
        # Usar dias desde o primeiro registro como feature
        base_date = self.df['data'].min()
        X = (self.df['data'] - base_date).dt.days.values.reshape(-1, 1)
        y = self.df['capacidade_percent'].values.reshape(-1, 1)
        
        # Escalonar
        X_scaled = self.scaler_x.fit_transform(X)
        y_scaled = self.scaler_y.fit_transform(y)
        
        # SVR com kernel RBF
        self.model = SVR(kernel='rbf', C=100, gamma='scale', epsilon=0.1)
        self.model.fit(X_scaled, y_scaled.ravel())
        
        return True
    
    def predict_future(self):
        """Prediz a capacidade futura até atingir o threshold."""
        if self.model is None:
            if not self.train_svr():
                return None, None
        
        base_date = self.df['data'].min()
        last_date = self.df['data'].max()
        
        # Criar datas futuras por até 3 anos
        future_days = np.arange(0, 1100, 7)  # até ~3 anos, passo semanal
        X_future = future_days.reshape(-1, 1)
        X_future_scaled = self.scaler_x.transform(X_future)
        y_pred_scaled = self.model.predict(X_future_scaled)
        y_pred = self.scaler_y.inverse_transform(y_pred_scaled.reshape(-1, 1)).ravel()
        
        # Encontrar quando atinge o threshold (80%)
        end_life_day = None
        for day, cap in zip(future_days, y_pred):
            if cap <= self.end_life_threshold:
                end_life_day = day
                break
        
        if end_life_day is not None:
            end_life_date = base_date + timedelta(days=int(end_life_day))
        else:
            end_life_date = None
        
        return y_pred, end_life_date
    
    def plot_and_predict(self):
        """Plota dados históricos + predição SVR e exibe data de fim de vida."""
        if self.df is None:
            messagebox.showerror("Erro", "Nenhum dado carregado. Carregue um CSV, capture estado atual ou gere exemplo.")
            return

        if not self.train_svr():
            return

        # Previsão
        y_pred, end_life_date = self.predict_future()

        # Preparar plot
        self.ax.clear()
        base_date = self.df['data'].min()
        last_date = self.df['data'].max()

        # Plot histórico
        self.ax.plot(self.df['data'], self.df['capacidade_percent'], 'bo-', label='Dados históricos', markersize=4)

        # Plot predição
        if y_pred is not None:
            future_days = np.arange(0, len(y_pred)*7, 7)  # passo semanal
            future_dates = [base_date + timedelta(days=int(d)) for d in future_days]
            self.ax.plot(future_dates, y_pred, 'r--', label='Predição SVR', linewidth=2)

        # Linha de limite (80%)
        self.ax.axhline(y=self.end_life_threshold, color='green', linestyle=':', label=f'Limite de fim de vida ({self.end_life_threshold}%)')

        # Marcar ponto de fim de vida
        if end_life_date and y_pred is not None and len(future_dates) > 0:
            # CORREÇÃO: encontrar o índice da data futura mais próxima ou igual a end_life_date
            # Converter future_dates para array de timestamps para comparação segura
            future_dates_array = np.array(future_dates)
            # Encontrar índice onde a data é >= end_life_date
            indices = np.where(future_dates_array >= end_life_date)[0]
            if len(indices) > 0:
                idx = indices[0]
                cap_at_end = y_pred[idx]
                self.ax.axvline(x=end_life_date, color='orange', linestyle='--', label=f'Fim de vida previsto: {end_life_date.strftime("%Y-%m-%d")}')
                self.ax.plot(end_life_date, cap_at_end, 'ro', markersize=8)
            else:
                # Caso não encontre (não deveria acontecer), apenas desenha a linha vertical sem ponto
                self.ax.axvline(x=end_life_date, color='orange', linestyle='--', label=f'Fim de vida previsto: {end_life_date.strftime("%Y-%m-%d")}')
        elif end_life_date:
            # Se não temos y_pred (improvável), apenas desenha a linha
            self.ax.axvline(x=end_life_date, color='orange', linestyle='--', label=f'Fim de vida previsto: {end_life_date.strftime("%Y-%m-%d")}')

        # Ajustes do gráfico
        self.ax.set_xlabel('Data')
        self.ax.set_ylabel('Capacidade da Bateria (%)')
        self.ax.set_title('Degradação da Bateria e Previsão com SVR')
        self.ax.legend(loc='best')
        self.ax.grid(True, linestyle=':', alpha=0.6)

        # Rotacionar labels de data para legibilidade
        self.figure.autofmt_xdate()

        self.canvas.draw()

        # Exibir resultado textual
        current_cap = self.df['capacidade_percent'].iloc[-1]
        if end_life_date:
            days_left = (end_life_date - datetime.now()).days
            if days_left < 0:
                result_text = f"⚠️ A bateria já atingiu o limite de {self.end_life_threshold}% (capacidade atual: {current_cap:.1f}%).\nRecomenda-se substituição."
            else:
                result_text = f"Capacidade atual: {current_cap:.1f}%\nPrevisão de fim de vida (≤{self.end_life_threshold}%): {end_life_date.strftime('%d/%m/%Y')}\nIsso equivale a aproximadamente {days_left} dias a partir de hoje."
        else:
            result_text = f"Capacidade atual: {current_cap:.1f}%\nCom base nos dados atuais, a bateria não atingirá {self.end_life_threshold}% nos próximos 3 anos."

        self.result_label.config(text=result_text)
        self.status_label.config(text=f"Análise concluída. Fim de vida previsto: {end_life_date.strftime('%Y-%m-%d') if end_life_date else 'não previsto em 3 anos'}")

if __name__ == "__main__":
    root = tk.Tk()
    app = BatteryAnalyzer(root)
    root.mainloop()