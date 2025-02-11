"""
advanced_visualizer.py
----------------------
Advanced visualizations for Garmin running data, including:
- Plotly dashboards
- Distributions
- Folium route map with pace-based color
"""

import plotly.graph_objects as go
import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMap, MarkerCluster
from folium import FeatureGroup

class AdvancedVisualizer:
    @staticmethod
    def create_interactive_dashboard(activity_data):
        """
        Build a multi-trace Plotly figure: HR, rolling HR, speed, power, etc.
        """
        df = activity_data['trackpoints']
        if df.empty or 'time' not in df.columns:
            return None

        fig = go.Figure()

        # Heart Rate
        if 'hr' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['time'],
                y=df['hr'],
                mode='lines',
                name='Heart Rate (bpm)',
                line=dict(color='red')
            ))
        # Rolling HR
        if 'hr_rolling' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['time'],
                y=df['hr_rolling'],
                mode='lines',
                name='HR Rolling (30s)',
                line=dict(color='orange', dash='dash')
            ))
        # Speed
        if 'speed' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['time'],
                y=df['speed']*3.6,
                mode='lines',
                name='Speed (km/h)',
                yaxis='y2',
                line=dict(color='green')
            ))
        # Power
        if 'power' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['time'],
                y=df['power'],
                mode='lines',
                name='Power (Watts)',
                yaxis='y3',
                line=dict(color='blue')
            ))

        fig.update_layout(
            title=dict(text='Running Activity Dashboard', x=0.5),
            template='plotly_dark',
            xaxis=dict(title='Time'),
            yaxis=dict(
                title=dict(text='HR (bpm)', font=dict(size=14, color='red')),
                side='left'
            ),
            yaxis2=dict(
                title=dict(text='Speed (km/h)', font=dict(size=14, color='green')),
                overlaying='y',
                side='right',
                anchor='x'
            ),
            yaxis3=dict(
                title=dict(text='Power (Watts)', font=dict(size=14, color='blue')),
                overlaying='y',
                side='left',
                anchor='free',
                position=0.06
            ),
            legend=dict(x=0, y=-0.2),
        )
        return fig

    @staticmethod
    def create_distribution_plots(activity_data):
        """
        Optional second figure: histogram distribution of HR / Pace.
        """
        df = activity_data['trackpoints']
        if df.empty:
            return None

        fig = go.Figure()

        if 'hr' in df.columns:
            fig.add_trace(go.Histogram(
                x=df['hr'].dropna(),
                nbinsx=30,
                name='HR Distribution',
                marker_color='red',
                opacity=0.5
            ))
        if 'pace' in df.columns:
            # pace in s/m => convert to min/km
            pace_s_per_km = df['pace'].dt.total_seconds() * 1000
            pace_min_km = pace_s_per_km / 60.0
            pace_min_km = pace_min_km.dropna()
            fig.add_trace(go.Histogram(
                x=pace_min_km,
                nbinsx=30,
                name='Pace (min/km)',
                marker_color='blue',
                opacity=0.5
            ))

        fig.update_layout(
            title=dict(text='Distributions: HR & Pace', x=0.5),
            template='plotly_dark',
            barmode='overlay',
            xaxis=dict(title='Value'),
            yaxis=dict(title='Count'),
        )
        fig.update_traces(opacity=0.75)
        return fig

    @staticmethod
    def create_route_map(activity_data):
        """
        Generate a Folium map colored by pace (or speed).
        We:
          - Extract lat/lon from trackpoints
          - Use pace or speed to determine color
          - Create color-coded line or markers
        Returns a folium.Map object.
        """
        df = activity_data['trackpoints']
        if df.empty or 'latitude' not in df.columns or 'longitude' not in df.columns:
            return None

        # Filter out rows with no lat/lon
        df = df.dropna(subset=['latitude', 'longitude']).reset_index(drop=True)
        if df.empty:
            return None

        # Decide which metric to color by: let's use speed in m/s
        # so we color from e.g. slow=blue to fast=red, or use a color scale
        df['speed_kmh'] = df['speed']*3.6  # convert m/s to km/h
        min_speed = df['speed_kmh'].min()
        max_speed = df['speed_kmh'].max()

        # If we have pace, we could invert colors, but let's keep speed
        # We'll define a helper to get color from speed
        def get_speed_color(spd):
            # Could do a simple linear interpolation or define bins
            # Example: 0 -> blue, mid -> yellow, high -> red
            ratio = (spd - min_speed) / (max_speed - min_speed + 1e-9)
            # ratio in [0..1]
            # let's do a naive approach:
            #   0 => [0,0,255], 1 => [255,0,0]
            r = int(255 * ratio)
            g = int(255 * (1 - ratio))
            b = 50  # keep a bit
            return f"#{r:02x}{g:02x}{b:02x}"

        # Create Folium map, center on first trackpoint
        start_lat = df.loc[0, 'latitude']
        start_lon = df.loc[0, 'longitude']
        m = folium.Map(location=[start_lat, start_lon], zoom_start=13)

        # We'll build a list of (lat, lon, color)
        route_points = []
        for i in range(len(df)):
            lat = df.loc[i, 'latitude']
            lon = df.loc[i, 'longitude']
            spd = df.loc[i, 'speed_kmh'] if not pd.isna(df.loc[i, 'speed_kmh']) else 0
            color = get_speed_color(spd)
            route_points.append((lat, lon, color))

        # We could create a polylinem, but we want a "colormap" effect. 
        # Approach: break route into short segments each with color
        coords = []
        for i in range(len(route_points)-1):
            lat1, lon1, col1 = route_points[i]
            lat2, lon2, col2 = route_points[i+1]
            seg = folium.PolyLine(
                locations=[(lat1, lon1), (lat2, lon2)],
                color=col1,
                weight=5,
                opacity=0.8
            )
            seg.add_to(m)

        # Add markers for start/end
        folium.Marker(
            location=[start_lat, start_lon],
            popup="Start",
            icon=folium.Icon(color="green", icon="play")
        ).add_to(m)
        end_lat = df.loc[len(df)-1, 'latitude']
        end_lon = df.loc[len(df)-1, 'longitude']
        folium.Marker(
            location=[end_lat, end_lon],
            popup="Finish",
            icon=folium.Icon(color="red", icon="stop")
        ).add_to(m)

        return m
