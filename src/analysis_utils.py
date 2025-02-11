"""
analysis_utils.py
-----------------
Additional or specialized analysis helpers for running data.
"""

import pandas as pd
import numpy as np
from datetime import timedelta

def estimate_vo2max_running(df):
    """
    Rough VO2max estimate for running using average speed & HR.
    """
    if df.empty or 'speed' not in df.columns or 'hr' not in df.columns:
        return None
    speed_mean = df['speed'].mean(skipna=True)  # m/s
    hr_mean = df['hr'].mean(skipna=True)
    if not speed_mean or not hr_mean:
        return None
    # Simplistic example: speed * 3.5 + (hr_mean / 10)
    vo2_est = speed_mean * 3.5 + (hr_mean / 10.0)
    return round(vo2_est, 2)

def calculate_running_intervals(df, pace_threshold_s_per_km=300):
    """
    Identify intervals faster than pace_threshold_s_per_km (5:00 min/km).
    Returns list of dicts with {start_idx, end_idx, distance_m, avg_pace}.
    """
    if df.empty or 'pace' not in df.columns:
        return []

    df['pace_s_per_km'] = df['pace'].dt.total_seconds() * 1000
    df['is_fast'] = df['pace_s_per_km'] < pace_threshold_s_per_km

    intervals = []
    in_interval = False
    start_idx = 0
    for i in range(len(df)):
        if df.loc[i, 'is_fast'] and not in_interval:
            in_interval = True
            start_idx = i
        elif in_interval and not df.loc[i, 'is_fast']:
            end_idx = i - 1
            subset = df.loc[start_idx:end_idx]
            total_dist = subset['distance_diff'].sum()
            avg_pace = subset['pace'].mean()
            intervals.append({
                'start_idx': start_idx,
                'end_idx': end_idx,
                'distance_m': round(total_dist, 1),
                'avg_pace': avg_pace
            })
            in_interval = False
    if in_interval:
        end_idx = len(df) - 1
        subset = df.loc[start_idx:end_idx]
        total_dist = subset['distance_diff'].sum()
        avg_pace = subset['pace'].mean()
        intervals.append({
            'start_idx': start_idx,
            'end_idx': end_idx,
            'distance_m': round(total_dist, 1),
            'avg_pace': avg_pace
        })
    return intervals

def calculate_average_pace_by_lap(laps):
    """
    Returns list of (lap_index, avg_pace_s_per_km).
    """
    results = []
    for i, lap in enumerate(laps):
        dist = lap.get('distance', 0)
        ttime = lap.get('total_time', 0)
        if dist > 0:
            pace_s_per_km = (ttime / (dist / 1000))
        else:
            pace_s_per_km = 0
        results.append((i+1, round(pace_s_per_km, 2)))
    return results

def calculate_aerobic_anaerobic_times(df, hr_zones):
    """
    Example: "Aerobic" = Zone 2-3, "Anaerobic" = Zone 4-5
    We approximate time spent by counting trackpoints in those zones * average time_diff.
    This is simplistic but you can refine as needed.
    """
    if df.empty or 'hr' not in df.columns:
        return {'aerobic_time_s': 0, 'anaerobic_time_s': 0}

    # We assume each row is a trackpoint with time_diff seconds
    df['zone'] = 'unknown'
    # Example: max HR = 190
    df.loc[df['hr'] < 190 * 0.6, 'zone'] = 'z1'  # <60%
    df.loc[(df['hr'] >= 190*0.6) & (df['hr'] < 190*0.8), 'zone'] = 'aerobic'
    df.loc[(df['hr'] >= 190*0.8), 'zone'] = 'anaerobic'

    # Sum time in each zone
    aerobic_time = df.loc[df['zone'] == 'aerobic', 'time_diff'].sum()
    anaerobic_time = df.loc[df['zone'] == 'anaerobic', 'time_diff'].sum()

    return {
        'aerobic_time_s': round(aerobic_time, 2),
        'anaerobic_time_s': round(anaerobic_time, 2)
    }

def estimate_running_efficiency(df):
    """
    Example "Running Efficiency" metric: ratio of speed to HR?
    Higher ratio => more efficient. Very rough approximation.
    """
    if df.empty or 'speed' not in df.columns or 'hr' not in df.columns:
        return None
    speed_mean = df['speed'].mean(skipna=True)
    hr_mean = df['hr'].mean(skipna=True)
    if not speed_mean or not hr_mean:
        return None
    # speed in m/s, HR in bpm => pure ratio is arbitrary
    return round(speed_mean / hr_mean, 4)

def estimate_stride_rate(df):
    """
    If 'cadence' is in steps/min or strides/min,
    we can compute average stride rate across the dataset.
    """
    if df.empty or 'cadence' not in df.columns:
        return None
    return round(df['cadence'].mean(skipna=True), 2)
