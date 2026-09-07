"""Generates SYNTHETIC theft case booking history, placeholder data until a
real theft dataset is provided. Sampled onto the real Division/Feeder_Name
values found in data/transformer_losses.xlsx (built by
scripts/build_transformer_losses.py) so it lines up with the real production
transformer-loss data for filtering and correlation analysis.

Run: python scripts/generate_sample_data.py
(Run build_transformer_losses.py first so real feeder/division names exist.)
"""
import os
import random

import numpy as np
import pandas as pd

random.seed(42)
np.random.seed(42)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
LOSSES_PATH = os.path.join(DATA_DIR, "transformer_losses.xlsx")

N_FEEDERS_SAMPLED = 60  # keep the synthetic dataset a manageable size

losses = pd.read_excel(LOSSES_PATH)
losses["Date"] = pd.to_datetime(losses["Date"])

START_DATE = losses["Date"].min().date()
END_DATE = (losses["Date"].max() + pd.offsets.MonthEnd(0)).date()  # cover the full last month
ALL_DAYS = pd.date_range(START_DATE, END_DATE, freq="D")

# --- Pick a sample of real (Division, Feeder_Name, Area_Type) combos, -------
# --- weighted by their real average loss % so synthetic theft intensity -----
# --- correlates with real losses (both driven by the same "risk" idea). -----
clean = losses[losses["Data_Quality_Flag"] == "OK"]
feeder_loss = (
    clean.groupby(["Division", "Feeder_Name", "Area_Type"], as_index=False)["Distribution_Loss_Pct"]
    .mean()
    .rename(columns={"Distribution_Loss_Pct": "avg_loss_pct"})
)

sampled = feeder_loss.sample(n=min(N_FEEDERS_SAMPLED, len(feeder_loss)), random_state=42).reset_index(drop=True)

lo, hi = sampled["avg_loss_pct"].min(), sampled["avg_loss_pct"].max()
sampled["risk_factor"] = 0.6 + 1.4 * (sampled["avg_loss_pct"] - lo) / max(hi - lo, 1e-9)

# --- Theft cases (daily booking history) --------------------------------------
THEFT_TYPES = ["Direct Tapping", "Meter Tampering", "Bypass", "Billing Fraud"]
STATUSES = ["Booked", "Under Investigation", "Penalty Recovered", "Closed"]

theft_rows = []
case_counter = 1
for _, feeder in sampled.iterrows():
    daily_case_prob = 0.025 * feeder.risk_factor
    for day in ALL_DAYS:
        if np.random.random() < daily_case_prob:
            n_cases_today = np.random.choice([1, 1, 1, 2], p=[0.7, 0.15, 0.1, 0.05])
            for _ in range(int(n_cases_today)):
                case_id = f"TC-{case_counter:05d}"
                case_counter += 1
                theft_type = random.choices(THEFT_TYPES, weights=[0.35, 0.3, 0.2, 0.15])[0]
                units_stolen = round(np.random.gamma(shape=2.0, scale=150 * feeder.risk_factor), 1)
                fine_amount = round(units_stolen * random.uniform(6, 12) + random.uniform(500, 3000), 0)
                status = random.choices(STATUSES, weights=[0.25, 0.2, 0.35, 0.2])[0]
                fir_filed = "Y" if theft_type in ("Direct Tapping", "Bypass") and random.random() < 0.6 else "N"

                theft_rows.append({
                    "Case_ID": case_id,
                    "Date": day.date(),
                    "Division": feeder.Division,
                    "Feeder_Name": feeder.Feeder_Name,
                    "Area_Type": feeder.Area_Type,
                    "Theft_Type": theft_type,
                    "Units_Stolen_kWh": units_stolen,
                    "Fine_Amount_INR": fine_amount,
                    "Case_Status": status,
                    "FIR_Filed": fir_filed,
                })

theft_cases_df = pd.DataFrame(theft_rows).sort_values("Date").reset_index(drop=True)

os.makedirs(DATA_DIR, exist_ok=True)
theft_cases_df.to_excel(os.path.join(DATA_DIR, "theft_cases.xlsx"), index=False)

print(f"theft_cases.xlsx: {len(theft_cases_df)} rows, {theft_cases_df['Feeder_Name'].nunique()} feeders (SYNTHETIC placeholder data)")
print(f"Date range: {START_DATE} to {END_DATE}")
print(f"Written to: {DATA_DIR}")
