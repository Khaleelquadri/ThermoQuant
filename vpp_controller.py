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
