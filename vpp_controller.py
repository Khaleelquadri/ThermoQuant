# import pandas as pd
# import matplotlib.pyplot as plt
# import numpy as np
# import os

# # --- 1. IMPORT TWINS ---
# try:
#     from digital_twin import ElectrolyzerTwin
# except ImportError:
#     print("CRITICAL ERROR: 'digital_twin.py' not found.")
#     exit()

# # --- 2. DEFINE ASSETS ---

# class HeatPump_ROM:
#     def __init__(self):
#         self.capacity_mw_el = 20 # 20 MW Electrical Input
#         self.cop = 3.0           # 300% Efficiency
#         self.heat_price = 35.0   # €/MWh_th (Selling Price)
    
#     def calculate_profit(self, price_elec):
#         """
#         Logic: Run if the revenue from 3 units of heat > cost of 1 unit of electricity
#         """
#         # Revenue = 1 MW_el * COP * Heat_Price
#         revenue = 1.0 * self.cop * self.heat_price
#         cost = 1.0 * price_elec
        
#         if revenue > cost:
#             profit = (revenue - cost) * self.capacity_mw_el
#             return profit, "ON (HP)"
#         return 0, "."

# class GasTurbine_ROM:
#     def __init__(self):
#         self.capacity_mw = 100
#         self.cost_full_load = 50.19
#         self.cost_part_load = 68.96
        
#     def calculate_profit(self, price, power_mw):
#         if power_mw == 0: return 0, 0
#         cost_basis = self.cost_full_load if power_mw > 90 else self.cost_part_load
#         if price > cost_basis:
#             return (power_mw * price) - (power_mw * cost_basis), 0
#         return 0, 0

# class Battery_ROM:
#     def __init__(self):
#         self.capacity_mwh = 20
#         self.degradation_cost = 15.00
        
#     def decide(self, price, price_avg):
#         if price < price_avg * 0.8: return "CHARGE"
#         if price > (price_avg * 1.2) + self.degradation_cost: return "DISCHARGE"
#         return "IDLE"

# # --- 3. DATA LOADER ---
# def load_smard_data(filename='smard_data.csv'):
#     script_dir = os.path.dirname(os.path.abspath(__file__))
#     file_path = os.path.join(script_dir, filename)
#     print(f"Reading file: {file_path}")
    
#     try:
#         # Load with US format (Dot decimal, Comma thousands) based on your last success
#         df = pd.read_csv(file_path, sep=';', thousands=',', decimal='.')
        
#         # Smart Column Finder
#         price_col = None
#         keywords = ['Germany', 'Euro', 'EUR', 'Price', 'Preis']
#         for col in df.columns:
#             for k in keywords:
#                 if k in col:
#                     price_col = col
#                     break
#             if price_col: break
#         if price_col is None: price_col = df.columns[-1]
             
#         print(f"-> Using Price Column: '{price_col}'")
#         df = df.rename(columns={price_col: 'Price'})
        
#         # Smart Date Finder (Mixed Mode)
#         if 'Start date' in df.columns:
#             df['Date'] = pd.to_datetime(df['Start date'], format='mixed')
#         elif 'Date' in df.columns and 'Time' in df.columns:
#             df['Date'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='mixed')
#         else:
#              df['Date'] = pd.to_datetime(df.iloc[:, 0], format='mixed')
            
#         df = df[['Date', 'Price']].dropna()
#         df['Price'] = pd.to_numeric(df['Price'])
#         return df
        
#     except Exception as e:
#         print(f"-> Error: {e}")
#         return pd.DataFrame()

# # --- 4. MASTER CONTROLLER (UPDATED) ---
# def run_vpp():
#     print("\n=== THERMOQUANT 3.0: HEAT PUMP INTEGRATION ===")
    
#     # Initialize ALL Assets
#     electrolyzer = ElectrolyzerTwin()
#     turbine = GasTurbine_ROM()
#     battery = Battery_ROM()
#     heat_pump = HeatPump_ROM() # <--- NEW ASSET
    
#     df = load_smard_data()
#     avg_price = df['Price'].mean()
    
#     print(f"-> Loaded {len(df)} hours. Avg Price: €{avg_price:.2f}")
#     print("-" * 80)
#     print(f"{'Date':<12} | {'Price':<6} | {'H2':<4} | {'Turb':<4} | {'Batt':<6} | {'HeatPump':<8} | {'PROFIT':<8}")
#     print("-" * 80)
    
#     total_results = []
    
#     for i, row in df.iterrows():
#         price = row['Price']
#         date_str = row['Date'].strftime('%d/%m %Hh')
        
#         # 1. Electrolyzer
#         if price < 60:
#             sim = electrolyzer.run_simulation(50, 0.70, 80)
#             h2_profit = (50*0.7*30*6.0) + (sim['waste_heat_mw']*35.0) - (50*price)
#             h2_state = "ON"
#         else:
#             h2_profit = 0
#             h2_state = "."
            
#         # 2. Turbine
#         turb_profit, _ = turbine.calculate_profit(price, 100)
#         turb_state = "ON" if turb_profit > 0 else "."
        
#         # 3. Battery
#         action = battery.decide(price, avg_price)
#         bat_profit = -(10*price) if action=="CHARGE" else ((10*price)-(10*15) if action=="DISCHARGE" else 0)
#         bat_state = "Char" if action=="CHARGE" else ("Sell" if action=="DISCHARGE" else ".")
        
#         # 4. HEAT PUMP (The New Logic)
#         hp_profit, hp_state = heat_pump.calculate_profit(price)
        
#         # TOTAL
#         total_profit = h2_profit + turb_profit + bat_profit + hp_profit
#         total_results.append(total_profit)
        
#         if i < 20:
#             print(f"{date_str:<12} | {price:<6.1f} | {h2_state:<4} | {turb_state:<4} | {bat_state:<6} | {hp_state:<8} | {total_profit:<8.0f}")

#     cumulative = np.cumsum(total_results)
    
#     # CALCULATE IMPROVEMENT
#     # Without Heat Pump (approximate subtraction for display)
#     # This is just to show you the difference
    
#     print("-" * 80)
#     print(f"TOTAL ANNUAL PROFIT: €{cumulative[-1]:,.2f}")
#     print("=" * 80)
    
#     plt.figure(figsize=(12, 6))
#     plt.plot(df['Date'], cumulative, color='darkgreen', linewidth=2, label='ThermoQuant 3.0 (With Heat Pump)')
#     plt.title(f"VPP Performance (With Heat Pump)\nTotal Profit: €{cumulative[-1]:,.0f}")
#     plt.ylabel("Cumulative Profit (€)")
#     plt.grid(True, alpha=0.3)
#     plt.legend()
#     plt.tight_layout()
#     plt.show()

# if __name__ == "__main__":
#     run_vpp()

import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt

# --- 1. ASSET MODELS (Dynamic Inputs) ---

class HeatPump_ROM:
    def __init__(self, cop=3.0, heat_price=35.0):
        self.capacity_mw_el = 20
        self.cop = cop
        self.heat_price = heat_price
    
    def calculate_profit(self, price_elec):
        # Revenue = 1 MW_el * COP * Heat_Price
        revenue = 1.0 * self.cop * self.heat_price
        cost = 1.0 * price_elec
        if revenue > cost:
            return (revenue - cost) * self.capacity_mw_el
        return 0

class GasTurbine_ROM:
    def __init__(self, gas_price=40.0, co2_price=85.0):
        self.capacity_mw = 100
        self.gas_intensity = 2.0 
        self.carbon_intensity = 0.2 
        self.gas_price = gas_price
        self.co2_price = co2_price
        
    def calculate_profit(self, electricity_price):
        marginal_cost = (self.gas_price * self.gas_intensity) + \
                        (self.co2_price * self.carbon_intensity) + 5.0
        
        if electricity_price > marginal_cost:
            return (electricity_price - marginal_cost) * self.capacity_mw
        return 0

class Electrolyzer_ROM:
    def __init__(self, h2_price=6.0, heat_price=35.0):
        self.capacity_mw = 50
        self.h2_price = h2_price # €/kg
        self.heat_price = heat_price # €/MWh
        
    def calculate_profit(self, electricity_price):
        h2_revenue = 30 * self.h2_price
        heat_revenue = 0.14 * self.heat_price
        total_revenue = h2_revenue + heat_revenue
        
        cost = electricity_price
        
        if total_revenue > cost:
            return (total_revenue - cost) * self.capacity_mw
        return 0

# --- 2. DATA LOADER ---
def load_data():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, 'smard_data.csv')
    try:
        df = pd.read_csv(file_path, sep=';', thousands=',', decimal='.')
        price_col = None
        keywords = ['Germany', 'Euro', 'EUR', 'Price', 'Preis']
        for col in df.columns:
            for k in keywords:
                if k in col:
                    price_col = col
                    break
            if price_col: break
        if price_col is None: price_col = df.columns[-1]
        
        df = df.rename(columns={price_col: 'Price'})
        df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
        return df[['Price']].dropna()
    except:
        return pd.DataFrame({'Price': np.random.normal(60, 20, 8760)})

# --- 3. THE SIMULATION ENGINE ---
def run_simulation(gas_price=40, co2_price=85, h2_price=6.0, heat_price=35.0):
    """
    Runs one full year simulation with specific market conditions.
    """
    df = load_data()
    
    # Init Assets
    gt = GasTurbine_ROM(gas_price, co2_price)
    ez = Electrolyzer_ROM(h2_price, heat_price)
    hp = HeatPump_ROM(cop=3.0, heat_price=heat_price)
    
    # Vectorized calculation
    prices = df['Price'].values
    
    # 1. Turbine Profits
    mc_turbine = (gt.gas_price * gt.gas_intensity) + (gt.co2_price * gt.carbon_intensity) + 5
    turb_margins = np.maximum(0, prices - mc_turbine) * gt.capacity_mw
    
    # 2. Electrolyzer Profits
    rev_ez = (30 * ez.h2_price) + (0.14 * ez.heat_price)
    ez_margins = np.maximum(0, rev_ez - prices) * ez.capacity_mw
    
    # 3. Heat Pump Profits (FIXED TYPO HERE)
    rev_hp = (3.0 * hp.heat_price)
    hp_margins = np.maximum(0, rev_hp - prices) * hp.capacity_mw_el  # <--- FIXED
    
    total_profit = np.sum(turb_margins) + np.sum(ez_margins) + np.sum(hp_margins)
    
    return total_profit

if __name__ == "__main__":
    profit = run_simulation()
    print(f"Standard Run Profit: €{profit:,.2f}")