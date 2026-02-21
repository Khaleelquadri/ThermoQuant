import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
from scipy.optimize import linprog

# --- 1. CONFIGURATION ---
BATTERY_CAPACITY = 20    # MWh
MAX_POWER = 10           # MW
EFFICIENCY = 0.90        # Round-trip efficiency
DEGRADATION_COST = 10.0  # €/MWh cycled

# --- 2. THE OPTIMIZER ENGINE (SciPy) ---
def optimize_day(prices):
    """
    Mathematically finds the perfect battery schedule for a 24-hour block.
    """
    hours = len(prices) 
    # c vector: Minimize Cost = (Charge * Price) - (Discharge * (Price - Degr))
    c = []
    for p in prices:
        c.append(p)                   
        c.append(-(p - DEGRADATION_COST)) 

    # Constraints Setup
    A_ub = []
    b_ub = []
    current_energy_coeffs = np.zeros(2 * hours)
    
    for t in range(hours):
        eff_factor = np.sqrt(EFFICIENCY)
        current_energy_coeffs[2*t] = eff_factor      # Charge input
        current_energy_coeffs[2*t+1] = -1/eff_factor # Discharge output
        
        # Energy must be <= Capacity
        A_ub.append(current_energy_coeffs.copy())
        b_ub.append(BATTERY_CAPACITY)
        
        # Energy must be >= 0
        A_ub.append(-current_energy_coeffs.copy())
        b_ub.append(0)

    bounds = [(0, MAX_POWER) for _ in range(2 * hours)]
    
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
    
    if res.success:
        return res.x[0::2], res.x[1::2] # Charge, Discharge
    else:
        return np.zeros(hours), np.zeros(hours)

# --- 3. ROBUST DATA LOADER (The Fix) ---
def load_data():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, 'smard_data.csv')
    print(f"Loading data from: {file_path}")

    try:
        # 1. Use the settings that WORKED: Semicolon sep, Comma thousands, Dot decimal
        df = pd.read_csv(file_path, sep=';', thousands=',', decimal='.')
        
        # 2. Smart Price Column Finder
        price_col = None
        keywords = ['Germany', 'Euro', 'EUR', 'Price', 'Preis']
        for col in df.columns:
            for k in keywords:
                if k in col:
                    price_col = col
                    break
            if price_col: break
        
        if price_col is None: 
            price_col = df.columns[-1]
            
        df = df.rename(columns={price_col: 'Price'})
        
        # 3. Smart Date Finder (The Critical Part)
        if 'Start date' in df.columns:
            df['Date'] = pd.to_datetime(df['Start date'], format='mixed')
        elif 'Date' in df.columns and 'Time' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='mixed')
        else:
             df['Date'] = pd.to_datetime(df.iloc[:, 0], format='mixed')

        # Clean up
        df = df[['Date', 'Price']].dropna()
        df['Price'] = pd.to_numeric(df['Price'])
        return df

    except Exception as e:
        print(f"CRITICAL ERROR LOADING DATA: {e}")
        return pd.DataFrame() # Return empty to prevent crash, handled in main

# --- 4. MAIN EXECUTION ---
def run_optimization():
    print("=== THERMOQUANT 5.0: MATHEMATICAL OPTIMIZER ===")
    df = load_data()
    
    if df.empty:
        print("ERROR: No data loaded. Please check smard_data.csv format.")
        return

    print(f"Optimizing {len(df)} hours using Linear Programming (SciPy)...")
    
    optimized_profits = []
    
    # Group by Day
    grouped = df.groupby(df['Date'].dt.date)
    
    for date, day_data in grouped:
        if len(day_data) < 24: continue 
        
        prices = day_data['Price'].values[:24]
        charge, discharge = optimize_day(prices)
        
        # Calculate Daily Profit
        daily_revenue = np.sum(discharge * prices)
        daily_cost = np.sum(charge * prices)
        daily_degradation = np.sum(discharge * DEGRADATION_COST)
        
        daily_profit = daily_revenue - daily_cost - daily_degradation
        optimized_profits.append(daily_profit)
        
        # Show sample output for the first day found
        if len(optimized_profits) == 1:
            print("-" * 60)
            print(f"OPTIMIZATION SAMPLE ({date})")
            print(f"{'Hour':<5} | {'Price':<6} | {'Charge':<6} | {'Dischg':<6}")
            print("-" * 60)
            for h in range(24):
                if charge[h] > 0.1 or discharge[h] > 0.1:
                    print(f"{h:<5} | {prices[h]:<6.1f} | {charge[h]:<6.1f} | {discharge[h]:<6.1f}")
            print("-" * 60)

    total_opt_profit = sum(optimized_profits)
    print(f"\nTOTAL OPTIMIZED BATTERY PROFIT: €{total_opt_profit:,.2f}")
    print("=================================================")

if __name__ == "__main__":
    run_optimization()