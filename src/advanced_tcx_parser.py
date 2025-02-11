"""
advanced_tcx_parser.py
----------------------
Parses TCX files, integrates advanced analytics from analysis_utils.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import warnings

from .analysis_utils import (
    estimate_vo2max_running,
    calculate_running_intervals,
    calculate_average_pace_by_lap,
    calculate_aerobic_anaerobic_times,
    estimate_running_efficiency,
    estimate_stride_rate
)

warnings.filterwarnings("ignore")

NS = {
    'ns': 'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2',
    'ns3': 'http://www.garmin.com/xmlschemas/ActivityExtension/v2',
    'ns5': 'http://www.garmin.com/xmlschemas/ActivityGoals/v1'
}

class AdvancedTcxParser:
    def __init__(self, tcx_file):
        self.tcx_file = tcx_file
        self.tree = ET.parse(tcx_file)
        self.root = self.tree.getroot()
        self.activity = self.root.find('.//ns:Activity', NS)

        self.trackpoint_df = self._parse_trackpoints()
        self.laps = self._parse_laps()
        self.metadata = self._parse_metadata()
        self.extended_stats = self._calculate_extended_stats()

        self.activity_data = {
            'metadata': self.metadata,
            'laps': self.laps,
            'trackpoints': self.trackpoint_df,
            'extended_stats': self.extended_stats
        }

    def _parse_metadata(self):
        return {
            'sport': self.activity.get('Sport', 'Unknown'),
            'id': self._safe_parse(lambda:
                datetime.fromisoformat(self.activity.find('.//ns:Id', NS).text)),
            'device': self._parse_device_info(),
            'start_time': self._safe_parse(lambda:
                datetime.fromisoformat(self.activity.find('.//ns:Lap', NS).attrib['StartTime'])),
            'training': self._parse_training_info()
        }

    def _parse_training_info(self):
        return {
            'vo2_max': self._safe_parse(lambda:
                float(self.root.find('.//ns5:vo2Max', NS).text)),
            'training_effect': self._safe_parse(lambda:
                float(self.root.find('.//ns3:TrainingEffect', NS).text)),
            'anaerobic_training_effect': self._safe_parse(lambda:
                float(self.root.find('.//ns3:AnaerobicTrainingEffect', NS).text))
        }

    def _parse_device_info(self):
        creator = self.root.find('.//ns:Creator', NS)
        if creator is not None:
            return {
                'name': self._safe_parse(lambda: creator.find('ns:Name', NS).text),
                'product_id': self._safe_parse(lambda: creator.find('ns:ProductID', NS).text),
                'version': self._parse_version(creator)
            }
        return {}

    def _parse_version(self, creator):
        version = creator.find('ns:Version', NS)
        if version is None:
            return {}
        return {
            'major': self._safe_parse(lambda: version.find('ns:VersionMajor', NS).text),
            'minor': self._safe_parse(lambda: version.find('ns:VersionMinor', NS).text)
        }

    def _parse_laps(self):
        laps = []
        for lap in self.activity.findall('ns:Lap', NS):
            laps.append({
                'start_time': self._safe_parse(lambda:
                    datetime.fromisoformat(lap.get('StartTime'))),
                'total_time': self._safe_parse(lambda:
                    float(lap.find('ns:TotalTimeSeconds', NS).text)),
                'distance': self._safe_parse(lambda:
                    float(lap.find('ns:DistanceMeters', NS).text)),
                'calories': self._safe_parse(lambda:
                    int(lap.find('ns:Calories', NS).text)),
                'intensity': self._safe_parse(lambda:
                    lap.find('ns:Intensity', NS).text),
                'trigger_method': self._safe_parse(lambda:
                    lap.find('ns:TriggerMethod', NS).text),
                'avg_hr': self._safe_parse(lambda:
                    int(lap.find('ns:AverageHeartRateBpm/ns:Value', NS).text)),
                'max_hr': self._safe_parse(lambda:
                    int(lap.find('ns:MaximumHeartRateBpm/ns:Value', NS).text)),
                'lap_metrics': self._parse_lap_extensions(lap)
            })
        return laps

    def _parse_lap_extensions(self, lap):
        return {
            'avg_speed': self._safe_parse(lambda:
                float(lap.find('ns:Extensions/ns3:LX/ns3:AvgSpeed', NS).text)),
            'max_speed': self._safe_parse(lambda:
                float(lap.find('ns:Extensions/ns3:LX/ns3:MaxSpeed', NS).text)),
            'avg_power': self._safe_parse(lambda:
                int(lap.find('ns:Extensions/ns3:LX/ns3:AvgWatts', NS).text))
        }

    def _parse_trackpoints(self):
        points = []
        for tp in self.activity.findall('.//ns:Trackpoint', NS):
            point = {
                'time': self._safe_parse(lambda:
                    datetime.fromisoformat(tp.find('ns:Time', NS).text)),
                'latitude': self._safe_parse(lambda:
                    float(tp.find('ns:Position/ns:LatitudeDegrees', NS).text)),
                'longitude': self._safe_parse(lambda:
                    float(tp.find('ns:Position/ns:LongitudeDegrees', NS).text)),
                'altitude': self._safe_parse(lambda:
                    float(tp.find('ns:AltitudeMeters', NS).text)),
                'distance': self._safe_parse(lambda:
                    float(tp.find('ns:DistanceMeters', NS).text)),
                'hr': self._safe_parse(lambda:
                    int(tp.find('ns:HeartRateBpm/ns:Value', NS).text)),
                'cadence': self._safe_parse(lambda:
                    int(tp.find('ns:Cadence', NS).text)),
                'power': self._safe_parse(lambda:
                    int(tp.find('ns:Extensions/ns3:TPX/ns3:Watts', NS).text)),
                'temperature': self._safe_parse(lambda:
                    float(tp.find('ns:Extensions/ns3:TPX/ns3:Temp', NS).text))
            }
            valid_data = {k: v for k, v in point.items() if v is not None}
            points.append(valid_data)

        df = pd.DataFrame(points)
        if df.empty:
            return df

        needed_cols = [
            "time","latitude","longitude","altitude","distance",
            "hr","cadence","power","temperature"
        ]
        for col in needed_cols:
            if col not in df.columns:
                df[col] = np.nan

        df = self._calculate_metrics(df)
        return df

    def _calculate_metrics(self, df):
        if df.empty:
            return df

        if len(df) == 1:
            df['time_diff'] = 0.0
            df['distance_diff'] = 0.0
            df['speed'] = np.nan
            df['pace'] = np.nan
            df['grade'] = np.nan
            df['power_hr_ratio'] = np.nan
            df['efficiency'] = np.nan
            df['hr_rolling'] = df['hr']
            df['power_rolling'] = df['power']
            return df

        df['time_diff'] = df['time'].diff().dt.total_seconds().fillna(0)
        df['distance_diff'] = df['distance'].diff().fillna(0)

        # Speed = m/s
        df['speed'] = (df['distance_diff'] / df['time_diff']).replace([np.inf, -np.inf], np.nan)

        df['pace'] = pd.to_timedelta(
            df['time_diff'] / df['distance_diff'].clip(lower=1e-6),
            unit='s'
        )

        df['grade'] = np.degrees(
            np.arctan(df['altitude'].diff() / df['distance_diff'].clip(lower=1e-6))
        ).fillna(0)

        df['power_hr_ratio'] = df['power'] / df['hr'].replace(0, np.nan)
        df['efficiency'] = df['distance_diff'] / (df['power'].replace(0, np.nan) + 1e-6)

        df['hr_rolling'] = df['hr'].rolling(window=30, min_periods=1).mean()
        df['power_rolling'] = df['power'].rolling(window=30, min_periods=1).mean()

        return df

    def _calculate_extended_stats(self):
        df = self.trackpoint_df
        laps = self.laps
        if df.empty:
            return {}

        elev_gain = df['altitude'].diff().clip(lower=0).sum()
        vo2_est = estimate_vo2max_running(df)
        intervals = calculate_running_intervals(df, pace_threshold_s_per_km=300)  # <5:00 min/km
        pace_by_lap = calculate_average_pace_by_lap(laps)

        return {
            'hr_zones': self._calculate_hr_zones(df),
            'power_zones': self._calculate_power_zones(df),
            'elevation_gain': elev_gain,
            'training_load': self._calculate_training_load(df),
            'recovery_time': self._estimate_recovery_time(df),
            'estimated_vo2max': vo2_est,
            'fast_intervals': intervals,
            'lap_paces': pace_by_lap
        }

    def _calculate_hr_zones(self, df):
        if 'hr' not in df.columns or df['hr'].dropna().empty:
            return {}
        max_hr = 190
        zones = {
            'Zone 1 (50-60%)': ((df['hr'] >= max_hr*0.5) & (df['hr'] < max_hr*0.6)).sum(),
            'Zone 2 (60-70%)': ((df['hr'] >= max_hr*0.6) & (df['hr'] < max_hr*0.7)).sum(),
            'Zone 3 (70-80%)': ((df['hr'] >= max_hr*0.7) & (df['hr'] < max_hr*0.8)).sum(),
            'Zone 4 (80-90%)': ((df['hr'] >= max_hr*0.8) & (df['hr'] < max_hr*0.9)).sum(),
            'Zone 5 (90-100%)': (df['hr'] >= max_hr*0.9).sum()
        }
        return zones

    def _calculate_power_zones(self, df):
        if 'power' not in df.columns or df['power'].dropna().empty:
            return {
                'Zone A (<150)': 0,
                'Zone B (150-250)': 0,
                'Zone C (250-350)': 0,
                'Zone D (350-450)': 0,
                'Zone E (450+)': 0
            }
        zones = {
            'Zone A (<150)': (df['power'] < 150).sum(),
            'Zone B (150-250)': ((df['power'] >= 150) & (df['power'] < 250)).sum(),
            'Zone C (250-350)': ((df['power'] >= 250) & (df['power'] < 350)).sum(),
            'Zone D (350-450)': ((df['power'] >= 350) & (df['power'] < 450)).sum(),
            'Zone E (450+)': (df['power'] >= 450).sum()
        }
        return zones

    def _calculate_training_load(self, df):
        if 'hr' not in df.columns or df['hr'].dropna().empty:
            return 0.0
        hr_mean = df['hr'].mean()
        time_sum = df['time_diff'].sum()
        load = (hr_mean * time_sum / 3600) * 0.01
        return round(load, 2)

    def _estimate_recovery_time(self, df):
        load = self._calculate_training_load(df)
        return timedelta(hours=load * 0.2)

    def _safe_parse(self, func):
        try:
            return func()
        except:
            return None


    def _calculate_extended_stats(self):
        df = self.trackpoint_df
        laps = self.laps
        if df.empty:
            return {}

        elev_gain = df['altitude'].diff().clip(lower=0).sum()
        vo2_est = estimate_vo2max_running(df)
        intervals = calculate_running_intervals(df, pace_threshold_s_per_km=300)
        pace_by_lap = calculate_average_pace_by_lap(laps)

        # NEW: Additional calls
        aerobic_anaerobic = calculate_aerobic_anaerobic_times(df, None)
        run_efficiency = estimate_running_efficiency(df)
        stride_rate = estimate_stride_rate(df)

        return {
            'hr_zones': self._calculate_hr_zones(df),
            'power_zones': self._calculate_power_zones(df),
            'elevation_gain': elev_gain,
            'training_load': self._calculate_training_load(df),
            'recovery_time': self._estimate_recovery_time(df),
            'estimated_vo2max': vo2_est,
            'fast_intervals': intervals,
            'lap_paces': pace_by_lap,
            'aerobic_anaerobic_times': aerobic_anaerobic,
            'running_efficiency': run_efficiency,
            'avg_stride_rate': stride_rate,
        }