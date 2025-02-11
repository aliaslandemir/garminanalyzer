"""
activity_database.py
--------------------
SQLite DB for storing activity summaries.
"""

import sqlite3
import numpy as np

class ActivityDatabase:
    def __init__(self, db_path='activities.db'):
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS activities (
                    id TEXT PRIMARY KEY,
                    sport TEXT,
                    start_time DATETIME,
                    duration REAL,
                    distance REAL,
                    avg_hr INTEGER,
                    max_hr INTEGER,
                    raw_data BLOB
                )
            ''')

    def save_activity(self, activity_data):
        metadata = activity_data['metadata']
        laps = activity_data['laps']

        total_duration = sum(lap.get('total_time', 0) or 0 for lap in laps)
        total_distance = sum(lap.get('distance', 0) or 0 for lap in laps)

        valid_avg_hrs = [lap['avg_hr'] for lap in laps if lap['avg_hr']]
        avg_hr = int(np.mean(valid_avg_hrs)) if valid_avg_hrs else 0

        valid_max_hrs = [lap['max_hr'] for lap in laps if lap['max_hr']]
        max_hr = max(valid_max_hrs) if valid_max_hrs else 0

        unique_id = str(metadata.get('start_time', 'Unknown'))

        with self.conn:
            self.conn.execute('''
                INSERT OR REPLACE INTO activities
                (id, sport, start_time, duration, distance, avg_hr, max_hr, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                unique_id,
                metadata.get('sport', 'Unknown'),
                metadata.get('start_time', None),
                total_duration,
                total_distance,
                avg_hr,
                max_hr,
                str(activity_data)
            ))

    def fetch_all_activities(self):
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM activities')
        return cur.fetchall()
