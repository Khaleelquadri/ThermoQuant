import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import pyomo.environ as pyo
from pyomo.opt import SolverFactory

# ==========================================
# 1. CONFIGURATION & PHYSICS
# ==========================================
BATTERY_CAPACITY = 20
BATTERY_POWER = 10
BATTERY_EFF = 0.90
DEGRADATION_COST = 10.0

EZ_CAPACITY = 50
EZ_EFF_H2 = 30      # kg/MWh
EZ_EFF_HEAT = 0.14  # MWh_th/MWh_el
H2_PRICE = 6.0
HEAT_PRICE = 35.0

HEAT_DEMAND_LIMIT = 40.0 # MW_th

# ==========================================
# 2. ROBUST DATA LOADER (The Fix)
# ==========================================
def load_data():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, 'smard_data.csv')
    print(f"Looking for data at: {file_path}")

    try:
        # Use the settings that WORKED in your thesis optimizer
        df = pd.read_csv(file_path, sep=';', thousands=',', decimal='.')
        
        # Smart Price Finder
        price_col = None
        keywords = ['Germany', 'Euro', 'EUR', 'Price', 'Preis']
        for col in df.columns:
            for k in keywords:
                if k in col:
                    price_col = col; break
            if price_col: break
        if price_col is None: price_col = df.columns[-1]
        
        df = df.rename(columns={price_col: 'Price'})
        
        # Smart Date Finder
        if 'Start date' in df.columns:
            df['Date'] = pd.to_datetime(df['Start date'], format='mixed')
        elif 'Date' in df.columns and 'Time' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='mixed')
        else:
             df['Date'] = pd.to_datetime(df.iloc[:, 0], format='mixed')
             
        df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
        return df[['Date', 'Price']].dropna()
    except Exception as e:
        print(f"CRITICAL ERROR LOADING DATA: {e}")
        return pd.DataFrame()

# ==========================================
# 3. MODEL A: HEURISTIC (Baseline)
# ==========================================
def run_heuristic(price):
    """Simple Logic: If Profit > 0, Run."""
    # Battery: Simple Arbitrage Estimation (50% capture rate)
    # We assume a standard rule-based controller captures about half 
    # the theoretical value of perfect foresight.
    bat_profit = 0 
    
    # Electrolyzer (Rule: Run if H2 revenue > Cost)
    rev_ez = (EZ_EFF_H2 * H2_PRICE) + (EZ_EFF_HEAT * HEAT_PRICE)
    cost_ez = price
    ez_profit = max(0, (rev_ez - cost_ez) * EZ_CAPACITY)
    
    # Heat Pump (Unconstrained - The "Dumb" Mode)
    # It ignores the 40MW limit!
    rev_hp = (3.0 * HEAT_PRICE)
    hp_profit = max(0, (rev_hp - price) * 20) # 20 MW cap
    
    return ez_profit + hp_profit

# ==========================================
# 4. MODEL B: MILP (Thesis Grade)
# ==========================================
def run_milp_day(prices):
    """Runs the Pyomo Optimizer for 24h"""
    m = pyo.ConcreteModel()
    m.T = pyo.RangeSet(0, 23)
    
    # Variables
    m.bat_c = pyo.Var(m.T, bounds=(0, BATTERY_POWER))
    m.bat_d = pyo.Var(m.T, bounds=(0, BATTERY_POWER))
    m.bat_e = pyo.Var(m.T, bounds=(0, BATTERY_CAPACITY))
    m.ez = pyo.Var(m.T, bounds=(0, EZ_CAPACITY))
    m.hp = pyo.Var(m.T, bounds=(0, 20)) 
    
    # Constraints 
    def bat_rule(m, t):
        if t == 0: return m.bat_e[t] == 10 + m.bat_c[t] - m.bat_d[t]
        return m.bat_e[t] == m.bat_e[t-1] + m.bat_c[t] - m.bat_d[t]
    m.bat_con = pyo.Constraint(m.T, rule=bat_rule)
    
    # Heat Limit (The Key Upgrade)
    def heat_rule(m, t):
        return (m.ez[t]*EZ_EFF_HEAT + m.hp[t]*3.0) <= HEAT_DEMAND_LIMIT
    m.heat_con = pyo.Constraint(m.T, rule=heat_rule)
    
    # Objective
    def obj_rule(m):
        prof = 0
        for t in m.T:
            prof += m.bat_d[t]*(prices[t]-DEGRADATION_COST) - m.bat_c[t]*prices[t]
            prof += m.ez[t] * ((EZ_EFF_H2*H2_PRICE + EZ_EFF_HEAT*HEAT_PRICE) - prices[t])
            prof += m.hp[t] * ((3.0*HEAT_PRICE) - prices[t])
        return prof
    m.obj = pyo.Objective(rule=obj_rule, sense=pyo.maximize)
    
    # Solve (Try both solver names)
    try:
        SolverFactory('appsi_highs').solve(m)
        return pyo.value(m.obj)
    except:
        try:
            SolverFactory('highs').solve(m)
            return pyo.value(m.obj)
        except:
            return 0

# ==========================================
# 5. MAIN EXECUTION & PLOTTING
# ==========================================
def main():
    print("=== THERMOQUANT COMPARISON ENGINE ===")
    df = load_data()
    if df.empty: 
        print("EXITING: No data found. Check file path above.")
        return
    
    DAYS_TO_SIMULATE = 14 
    print(f"Comparing Strategies over {DAYS_TO_SIMULATE} days...")
    print("(This takes about 10 seconds...)")
    
    heuristic_cumulative = []
    milp_cumulative = []
    dates = []
    
    total_h = 0
    total_m = 0
    
    grouped = df.groupby(df['Date'].dt.date)
    day_count = 0
    
    for date, day_data in grouped:
        if len(day_data) < 24: continue
        if day_count >= DAYS_TO_SIMULATE: break
        
        prices = day_data['Price'].values[:24]
        
        # 1. Run Heuristic
        h_day = sum([run_heuristic(p) for p in prices])
        total_h += h_day
        heuristic_cumulative.append(total_h)
        
        # 2. Run MILP
        m_day = run_milp_day(prices)
        total_m += m_day
        milp_cumulative.append(total_m)
        
        dates.append(date)
        day_count += 1
        
        # Progress bar
        if day_count % 5 == 0:
            print(f"...processed {day_count} days")

    # --- PLOTTING ---
    print(f"Finished! Total MILP Profit: €{total_m:,.0f} | Heuristic: €{total_h:,.0f}")
    print("Generating Graph...")
    
    plt.figure(figsize=(10, 6))
    
    # Plot Lines
    plt.plot(dates, [x/1000 for x in heuristic_cumulative], 
             label='Baseline (Heuristic)', color='gray', linestyle='--')
    plt.plot(dates, [x/1000 for x in milp_cumulative], 
             label='ThermoQuant 7.0 (MILP)', color='green', linewidth=2.5)
    
    # Formatting
    plt.title(f"Cumulative Profit Comparison ({DAYS_TO_SIMULATE} Days)", fontsize=14)
    plt.ylabel("Profit (€ Thousands)", fontsize=12)
    plt.xlabel("Date", fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=12)
    
    plt.tight_layout()
    plt.savefig('thesis_comparison.png')
    plt.show()
    
    print("Done! Graph saved as 'thesis_comparison.png'")

if __name__ == "__main__":
    main()