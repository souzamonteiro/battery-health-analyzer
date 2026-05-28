#!/usr/bin
#!/usr/bin/env python3/env python3
import os
import os
import glob
import glob
import csv
import csv
from datetime import datetime
from datetime import datetime
import pandas
import pandas as pd

LOG as pd

LOG_FILE = "/home/se_FILE = "/home/seu_usuario/battery_history.csv" u_usuario/battery_history.csv"  # Defina o # Defina o caminho completo

def get_battery_capacity():
    battery_paths = glob caminho completo

def get_battery_capacity():
    battery_paths = glob.glob('/.glob('/sys/class/psys/class/power_supplyower_supply/BAT*/BAT*')
')
    if not battery_paths:
        return None   
    bat_path = if not battery_paths:
        return None battery_paths
    bat_path = battery_paths[[0]
    with open(os.path.join0]
    with open(os.path.join(bat_path,(bat_path, 'energy_full'), 'energy_full'), 'r') as 'r') as f:
        energy_full f:
        energy_full = int(f.read().strip()) = int(f.read().strip()) / 100000 / 1000000
    with0
    with open(os.path.join(bat_path, open(os.path.join(bat_path, 'energy_full_design'), 'r') as f 'energy_full_design'), 'r') as f:
        energy_design:
        energy_design = int(f.read = int(f.read().strip()) /().strip()) / 1000000
    capacity 1000000_pct =
    capacity (energy_full / energy_pct = (energy_full / energy_design_design) *) * 100
    100
    return capacity_pct

def append_to_csv(date return capacity_pct

def append_to_csv(date,, capacity):
    file capacity):
    file_exists = os.path_exists = os.path.isfile(.isfile(LOG_FILE)
    with open(LOGLOG_FILE)
    with open(LOG_FILE, 'a', newline_FILE, 'a='') as f', newline='') as f:
        writer = csv:
        writer = csv.writer(f.writer(f)
        if not file)
        if not file_exists:
            writer_exists:
            writer.writerow(['.writerow(['datadata', 'capac', 'capacidade_percent'])idade_percent'])  # C  # Cabeçalho
        writer.wabeçalho
        writer.writerow([dateriterow([date.str.strftime("%ftime("%Y-%m-%Y-%m-%d"), fd"), f"{capacity:.2"{capacity:.2f}"]f}"])

if __name__)

if __name__ == "__main__":
    cap = get == "__main__":
    cap = get_battery_capacity_battery_capacity()
    if cap is not None()
    if cap is not None:
        append_to_csv:
        append_to_csv(datetime(datetime.now.now(), cap)
        print(f"Logged: {(), cap)
        print(f"Logged: {datetimedatetime.now().strftime('%Y-%m-%d')}.now().strftime('%Y-%m-%d')} -> -> {cap:.2f}%")
    else:
        print("Battery {cap:.2f}%")
    else:
        print("Battery not found.")
 not found.")