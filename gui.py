#!/usr/bin/env python
"""
gui.py
------
A fully extended CustomTkinter GUI for the Garmin Running Analyzer:

Key Features:
- Icons in top panel (icons/: open.png, pdf.png, compare.png, training.png, route.png)
- Up to 4-column multi-activity dashboard
- Single-activity Plotly charts (HR, Pace, Elevation) in browser
- Route Analysis, PDF Export, Training Load, Compare 2/4
- Temperature & Location data (via geopy)
- Removes "Moving Time" from main rows
- Dark/Green theme, asynchronous loading
"""

import tkinter as tk
from tkinter import Menu, filedialog, messagebox
import customtkinter as ctk
import queue
import threading
import tempfile
import webbrowser
import os
import numpy as np
import pandas as pd
from datetime import timedelta
from geopy.geocoders import Nominatim
from PIL import Image

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Local modules
from src.advanced_tcx_parser import AdvancedTcxParser
from src.activity_database import ActivityDatabase
from src.advanced_visualizer import AdvancedVisualizer

# Appearance setup
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

class GarminUltimateAnalyzer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Garmin Ultimate Analyzer")
        self.geometry("1920x1080")

        # Data structures
        self.activities = {}      # path -> activity_data
        self.db = ActivityDatabase()
        self.parse_queue = queue.Queue()

        # For location geocoding
        self.geolocator = Nominatim(user_agent="garmin-analyzer")

        # Load icons
        self.icons = {}
        self._load_icons()

        # Build UI
        self._create_menu()
        self._setup_ui()
        self._setup_bindings()

        # Periodically check parse queue
        self._poll_parse_queue()

    # ------------------------------------------------------
    # Icon loading
    # ------------------------------------------------------
    def _load_icons(self):
        """
        Attempt to load icons from 'icons/' folder.
        If missing, use a gray placeholder.
        """
        icon_files = {
            'open': 'open.png',
            'pdf': 'pdf.png',
            'compare': 'compare.png',
            'training': 'training.png',
            'route': 'route.png'
        }
        for key, filename in icon_files.items():
            self.icons[key] = self._attempt_load_icon(filename)

    def _attempt_load_icon(self, filename):
        try:
            path = os.path.join("icons", filename)
            img = Image.open(path)
            return ctk.CTkImage(light_image=img, dark_image=img, size=(24,24))
        except:
            # Gray placeholder if fail
            placeholder = Image.new('RGB', (24,24), color='gray')
            return ctk.CTkImage(light_image=placeholder, dark_image=placeholder, size=(24,24))

    # ------------------------------------------------------
    # Menu
    # ------------------------------------------------------
    def _create_menu(self):
        main_menu = Menu(self, tearoff=0)

        file_menu = Menu(main_menu, tearoff=0)
        file_menu.add_command(label="Open TCX", command=self.load_tcx)
        file_menu.add_command(label="Export PDF", command=self.export_pdf)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)

        analysis_menu = Menu(main_menu, tearoff=0)
        analysis_menu.add_command(label="Compare Activities", command=self.show_comparison)
        analysis_menu.add_command(label="Training Load Analysis", command=self.show_training_load)

        main_menu.add_cascade(label="File", menu=file_menu)
        main_menu.add_cascade(label="Analysis", menu=analysis_menu)
        self.config(menu=main_menu)

    # ------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------
    def _setup_ui(self):
        # Top control panel
        self.top_panel = ctk.CTkFrame(self, height=60)
        self.top_panel.pack(fill="x", padx=10, pady=5)
        self._build_top_panel()

        # Main content
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.pack(fill="both", expand=True)

        self.main_frame.columnconfigure(0, weight=0, minsize=350)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self.main_frame, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # Tabs on the right
        self.content_frame = ctk.CTkFrame(self.main_frame, corner_radius=0)
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        # Build components
        self._build_sidebar()
        self._build_tabs()

        # Status bar
        self.status_bar = ctk.CTkLabel(self, text="Ready", anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)

    def _build_top_panel(self):
        button_params = {
            'height': 40,
            'width': 200,
            'font': ctk.CTkFont(size=14, weight="bold"),
            'corner_radius': 8
        }
        top_buttons = [
            ("Open TCX", self.icons['open'], self.load_tcx),
            ("Export PDF", self.icons['pdf'], self.export_pdf),
            ("Compare Activities", self.icons['compare'], self.show_comparison),
            ("Training Load", self.icons['training'], self.show_training_load),
            ("Route Analysis", self.icons['route'], self.show_route_analysis),
        ]
        for col, (txt, icon, cmd) in enumerate(top_buttons):
            self.top_panel.grid_columnconfigure(col, weight=1, uniform="top_col")
            ctk.CTkButton(
                self.top_panel, text=txt, image=icon, command=cmd, **button_params
            ).grid(row=0, column=col, padx=5, pady=5, sticky="ew")

    def _build_sidebar(self):
        ctk.CTkLabel(
            self.sidebar,
            text="Activities",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(padx=10, pady=(10,5))

        self.search_entry = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="Search...",
            font=ctk.CTkFont(size=14)
        )
        self.search_entry.pack(fill="x", padx=10, pady=(0,10))

        self.act_list = tk.Listbox(
            self.sidebar,
            selectmode=tk.EXTENDED,
            bg='#2b2b2b',
            fg='white',
            font=('TkDefaultFont',14),
            height=25
        )
        self.act_list.pack(fill="both", expand=True, padx=10, pady=5)

        # Right-click
        self.list_menu = tk.Menu(self.sidebar, tearoff=0)
        self.list_menu.add_command(label="Show Details", command=self.show_details)
        self.list_menu.add_command(label="Delete", command=self.delete_activity)

    def _build_tabs(self):
        self.tabview = ctk.CTkTabview(self.content_frame)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.dashboard_tab = self.tabview.add("Dashboard")
        self.map_tab = self.tabview.add("Route Analysis")
        self.comp_tab = self.tabview.add("Comparison")

        self.dashboard_container = ctk.CTkFrame(self.dashboard_tab)
        self.dashboard_container.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            self.map_tab,
            text="Select an activity and then click 'Route Analysis' above.",
            font=ctk.CTkFont(size=14),
            justify=tk.CENTER
        ).pack(expand=True)

        ctk.CTkLabel(
            self.comp_tab,
            text="Use 'Compare Activities' if exactly 2 or 4 are selected,\n"
                 "or select up to 4 for side-by-side dashboard columns.",
            font=ctk.CTkFont(size=14),
            justify=tk.CENTER
        ).pack(expand=True)

    # ------------------------------------------------------
    # Binding
    # ------------------------------------------------------
    def _setup_bindings(self):
        self.act_list.bind('<<ListboxSelect>>', self.on_activity_select)
        self.act_list.bind("<Button-3>", self.show_list_menu)
        self.search_entry.bind("<KeyRelease>", self.filter_activities)

    # ------------------------------------------------------
    # Poll parse queue
    # ------------------------------------------------------
    def _poll_parse_queue(self):
        while not self.parse_queue.empty():
            path, parser_or_error = self.parse_queue.get()
            if isinstance(parser_or_error, Exception):
                self.show_error(f"Error loading {os.path.basename(path)}: {parser_or_error}")
            else:
                act_data = parser_or_error.activity_data
                self.db.save_activity(act_data)
                self.activities[path] = act_data
                # Insert name
                self.act_list.insert(tk.END, os.path.basename(path))
                self.update_status(f"Loaded: {os.path.basename(path)}")
        self.after(200, self._poll_parse_queue)

    # ------------------------------------------------------
    # Right-click menu
    # ------------------------------------------------------
    def show_list_menu(self, event):
        widget = event.widget
        idx = widget.nearest(event.y)
        if 0<= idx < len(self.act_list.get(0,tk.END)):
            self.act_list.selection_clear(0, tk.END)
            self.act_list.selection_set(idx)
        try:
            self.list_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.list_menu.grab_release()

    # ------------------------------------------------------
    # Load TCX
    # ------------------------------------------------------
    def load_tcx(self):
        files = filedialog.askopenfilenames(filetypes=[("TCX Files","*.tcx")])
        if not files:
            return
        def parse_file(path):
            try:
                parser = AdvancedTcxParser(path)
                self.parse_queue.put((path, parser))
            except Exception as e:
                self.parse_queue.put((path, e))
        for f in files:
            t=threading.Thread(target=parse_file, args=(f,), daemon=True)
            t.start()

    # ------------------------------------------------------
    # Searching
    # ------------------------------------------------------
    def filter_activities(self, event=None):
        term = self.search_entry.get().lower()
        self.act_list.delete(0, tk.END)
        for path in self.activities.keys():
            fname = os.path.basename(path).lower()
            if term in fname:
                self.act_list.insert(tk.END, os.path.basename(path))

    # ------------------------------------------------------
    # Single or Multi Activity => show in dashboard
    # ------------------------------------------------------
    def on_activity_select(self, event):
        sel = self.act_list.curselection()
        if not sel:
            return

        if len(sel)==1:
            path = list(self.activities.keys())[sel[0]]
            act_data = self.activities[path]
            # open interactive plot in browser
            self._open_interactive_plot(act_data)

            # Show single column
            acts_dict = { path: act_data }
            self._show_dashboard_activities(acts_dict)
        else:
            # up to 4 columns
            selected_dict = {}
            for i, idx in enumerate(sel):
                if i>=4:
                    break
                p= list(self.activities.keys())[idx]
                selected_dict[p] = self.activities[p]
            self._show_dashboard_activities(selected_dict)

    def _open_interactive_plot(self, activity):
        """
        Creates the interactive Plotly chart & distribution in new browser tabs
        """
        fig = AdvancedVisualizer.create_interactive_dashboard(activity)
        if fig:
            import tempfile
            html_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
            fig.write_html(html_file.name)
            webbrowser.open_new_tab(f"file://{html_file.name}")

        fig_dist = AdvancedVisualizer.create_distribution_plots(activity)
        if fig_dist:
            import tempfile
            html_file2 = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
            fig_dist.write_html(html_file2.name)
            webbrowser.open_new_tab(f"file://{html_file2.name}")

    def _show_dashboard_activities(self, acts_dict):
        """
        Clear the dashboard, then show up to 4 columns side by side.
        """
        for widget in self.dashboard_container.winfo_children():
            widget.destroy()

        n= min(len(acts_dict),4)
        for i in range(n):
            self.dashboard_container.columnconfigure(i,weight=1,uniform="dashcol")

        col=0
        for path, data in list(acts_dict.items())[:n]:
            self._create_dashboard_column(col, path, data)
            col+=1

    def _create_dashboard_column(self, col_index, path, data):
        # Summaries
        laps= data['laps']
        total_time= sum(l.get('total_time',0) for l in laps)
        total_dist= sum(l.get('distance',0) for l in laps)
        total_cal= sum(l.get('calories',0) for l in laps)
        elev= data['extended_stats'].get('elevation_gain',0)

        ex= self._compute_extra_metrics(data)
        meta_title = data['metadata'].get('title') or os.path.basename(path)

        col_frame = ctk.CTkFrame(self.dashboard_container)
        col_frame.grid(row=0, column=col_index, padx=10, pady=10, sticky="nsew")

        # row1
        row1 = ctk.CTkFrame(col_frame)
        row1.pack(fill="x", padx=5, pady=5)
        self._create_metric_card(row1, "Duration", f"{round(total_time,2)} s")
        self._create_metric_card(row1, "Distance", f"{round(total_dist,2)} m")
        self._create_metric_card(row1, "Elevation", f"{round(elev,2)} m")
        self._create_metric_card(row1, "Calories", str(total_cal))

        # row2
        row2= ctk.CTkFrame(col_frame)
        row2.pack(fill="x", padx=5, pady=5)
        avg_hr_txt= f"{ex['avg_hr']} bpm" if ex['avg_hr'] else "--"
        max_hr_txt= f"{ex['max_hr']} bpm" if ex['max_hr'] else "--"
        pace_txt= ex['avg_pace'] if ex['avg_pace'] else "--"
        elapsed_txt= ex['elapsed_time'] if ex['elapsed_time'] else "--"

        self._create_metric_card(row2,"Avg HR",avg_hr_txt)
        self._create_metric_card(row2,"Max HR",max_hr_txt)
        self._create_metric_card(row2,"Avg Pace",pace_txt)
        self._create_metric_card(row2,"Elapsed",elapsed_txt)

        # White/Red panel
        fancy= ctk.CTkFrame(col_frame,fg_color="white")
        fancy.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(
            fancy,
            text=meta_title,
            text_color="red",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(5,0))

        lines=[]
        if ex['location']:
            lines.append(f"Location: {ex['location']}")
        if ex['avg_temp'] is not None:
            lines.append(f"Avg Temp: {ex['avg_temp']} °C")
        lines.append(f"Sport: {data['metadata'].get('sport','Unknown')}")

        if not lines:
            lines.append("No location or temperature data.")

        ctk.CTkLabel(
            fancy,
            text="\n".join(lines),
            justify="left",
            text_color="red",
            font=ctk.CTkFont(size=14)
        ).pack(pady=(0,5))

    def _create_metric_card(self, parent, title, value):
        frame = ctk.CTkFrame(parent, width=120, height=60)
        frame.pack_propagate(False)
        frame.pack(side=tk.LEFT, padx=5, pady=5)

        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=12)).pack(pady=(5,0))
        ctk.CTkLabel(frame, text=value, font=ctk.CTkFont(size=16, weight="bold")).pack(expand=True)

    # ------------------------------------------------------
    # Additional Metrics (location, temp, hr, pace)
    # ------------------------------------------------------
    def _compute_extra_metrics(self, activity):
        df = activity.get('trackpoints', pd.DataFrame())
        if df.empty or 'time' not in df.columns:
            return {
                'avg_hr':None,'max_hr':None,'avg_pace':None,'elapsed_time':None,
                'avg_temp':None,'location':None
            }

        # HR
        if 'hr' in df.columns and not df['hr'].dropna().empty:
            avg_hr= round(df['hr'].mean(),1)
            max_hr= int(df['hr'].max())
        else:
            avg_hr,max_hr= None,None

        # Pace
        pace_str=None
        elapsed_str=None
        if len(df)>1:
            total_time_sec= (df['time'].iloc[-1] - df['time'].iloc[0]).total_seconds()
            dist_start= df['distance'].iloc[0]
            dist_end= df['distance'].iloc[-1]
            total_dist= dist_end - dist_start
            if total_dist>1 and total_time_sec>1:
                pace_s_per_m = total_time_sec / total_dist
                pace_min_km  = pace_s_per_m*1000 / 60
                pm= int(pace_min_km)
                ps= int((pace_min_km - pm)*60)
                pace_str= f"{pm}:{ps:02d} min/km"
                elapsed_str= str(timedelta(seconds=int(total_time_sec)))

        # Temperature
        if 'temperature' in df.columns and not df['temperature'].dropna().empty:
            avg_temp= round(df['temperature'].mean(),1)
        else:
            avg_temp=None

        # Location from first lat/lon
        location_str=None
        if 'latitude' in df.columns and 'longitude' in df.columns:
            valid= df[['latitude','longitude']].dropna()
            if not valid.empty:
                lat= valid.iloc[0]['latitude']
                lon= valid.iloc[0]['longitude']
                try:
                    rev= self.geolocator.reverse(f"{lat}, {lon}")
                    if rev:
                        location_str= rev.address
                except:
                    pass

        return {
            'avg_hr': avg_hr,
            'max_hr': max_hr,
            'avg_pace': pace_str,
            'elapsed_time': elapsed_str,
            'avg_temp': avg_temp,
            'location': location_str
        }

    # ------------------------------------------------------
    # Show Details, PDF, etc.
    # ------------------------------------------------------
    def show_details(self):
        sel= self.act_list.curselection()
        if not sel:
            return
        path= list(self.activities.keys())[sel[0]]
        data= self.activities[path]

        laps= data['laps']
        total_dur= sum(l.get('total_time',0) for l in laps)
        total_dist= sum(l.get('distance',0) for l in laps)
        total_cal= sum(l.get('calories',0) for l in laps)

        detail_win= ctk.CTkToplevel(self)
        detail_win.title("Activity Details")
        detail_win.geometry("500x400")

        txt= f"""
Sport: {data['metadata'].get('sport','Unknown')}
Start Time: {data['metadata'].get('start_time','N/A')}
Duration (s): {round(total_dur,2)}
Distance (m): {round(total_dist,2)}
Calories: {total_cal}
VO2 Max: {data['metadata']['training'].get('vo2_max','N/A')}
Training Effect: {data['metadata']['training'].get('training_effect','N/A')}

Extended Stats:
{data.get('extended_stats',{})}
"""
        ctk.CTkLabel(detail_win, text=txt, justify="left").pack(fill="both", expand=True, padx=20, pady=20)

    def show_route_analysis(self):
        sel= self.act_list.curselection()
        if not sel:
            messagebox.showinfo("Route Analysis","No activity selected.")
            return
        path= list(self.activities.keys())[sel[0]]
        data= self.activities[path]

        rmap= AdvancedVisualizer.create_route_map(data)
        if not rmap:
            self.show_error("No valid lat/long data for route.")
            return

        import tempfile
        html_file= tempfile.NamedTemporaryFile(delete=False, suffix='.html')
        rmap.save(html_file.name)
        webbrowser.open_new_tab(f"file://{html_file.name}")

    def show_comparison(self):
        sel= self.act_list.curselection()
        n= len(sel)
        if n not in [2,4]:
            messagebox.showwarning("Compare Activities","Select exactly 2 or 4.")
            return

        comp_win= ctk.CTkToplevel(self)
        comp_win.title("Activity Comparison")

        if n==2:
            comp_win.geometry("800x400")
            comp_win.columnconfigure(0, weight=1)
            comp_win.columnconfigure(1, weight=1)
            comp_win.rowconfigure(0, weight=1)
        else:
            comp_win.geometry("800x600")
            comp_win.columnconfigure(0, weight=1)
            comp_win.columnconfigure(1, weight=1)
            comp_win.rowconfigure(0, weight=1)
            comp_win.rowconfigure(1, weight=1)

        row,col=0,0
        for idx in sel:
            path= list(self.activities.keys())[idx]
            data= self.activities[path]
            name= os.path.basename(path)

            laps= data['laps']
            dur= sum(l.get('total_time',0) for l in laps)
            dist= sum(l.get('distance',0) for l in laps)
            cal= sum(l.get('calories',0) for l in laps)
            elev= data['extended_stats'].get('elevation_gain',0)
            ex= self._compute_extra_metrics(data)

            frame= ctk.CTkFrame(comp_win, corner_radius=10, fg_color="gray20")
            frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            ctk.CTkLabel(frame, text=name, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)

            inf=(
                f"Duration: {round(dur,2)} s\n"
                f"Distance: {round(dist,2)} m\n"
                f"Elevation: {round(elev,2)} m\n"
                f"Calories: {cal}\n\n"
            )
            if ex['avg_hr'] is not None:
                inf+=f"Avg HR: {ex['avg_hr']} bpm\n"
            if ex['max_hr'] is not None:
                inf+=f"Max HR: {ex['max_hr']} bpm\n"
            if ex['avg_pace']:
                inf+=f"Pace: {ex['avg_pace']}\n"
            if ex['elapsed_time']:
                inf+=f"Elapsed Time: {ex['elapsed_time']}\n"
            if ex['avg_temp'] is not None:
                inf+=f"Avg Temp: {ex['avg_temp']} °C\n"
            if ex['location']:
                inf+=f"Location: {ex['location']}\n"

            ctk.CTkLabel(frame, text=inf, justify="left").pack(padx=10,pady=5)

            col+=1
            if col>1:
                col=0
                row+=1

    def export_pdf(self):
        file_path= filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files","*.pdf")]
        )
        if not file_path:
            return
        try:
            c= canvas.Canvas(file_path, pagesize=letter)
            c.setFont("Helvetica",12)

            sel= self.act_list.curselection()
            if sel:
                path= list(self.activities.keys())[sel[0]]
                data= self.activities[path]
                laps= data['laps']
                dur= sum(l.get('total_time',0) for l in laps)
                dist= sum(l.get('distance',0) for l in laps)

                c.drawString(100,750,f"Activity Report: {data['metadata'].get('sport','Unknown')}")
                c.drawString(100,730,f"Date: {data['metadata'].get('start_time','N/A')}")
                c.drawString(100,710,f"Duration: {round(dur,2)} s")
                c.drawString(100,690,f"Distance: {round(dist,2)} m")
                c.drawString(100,670,f"Extended Stats: {data.get('extended_stats',{})}")

            c.save()
            self.update_status(f"Exported PDF to {file_path}")
        except Exception as e:
            self.show_error(f"PDF Export Error: {str(e)}")

    def show_training_load(self):
        if not self.activities:
            messagebox.showinfo("Training Load","No activities loaded.")
            return
        import plotly.graph_objects as go
        fig= go.Figure()
        for path, data in self.activities.items():
            st= data['metadata'].get('start_time',None)
            tl= data['extended_stats'].get('training_load',None)
            if st and tl is not None:
                fig.add_trace(go.Scatter(
                    x=[st], y=[tl],
                    name=os.path.basename(path),
                    mode='markers+text',
                    text=[os.path.basename(path)],
                    textposition='top center'
                ))
        fig.update_layout(title="Training Load Comparison", template='plotly_dark')
        fig.show()

    def delete_activity(self):
        sel= self.act_list.curselection()
        if not sel:
            return
        confirm= messagebox.askyesno("Confirm Delete","Are you sure you want to delete these activities?")
        if confirm:
            for s in reversed(sel):
                key= list(self.activities.keys())[s]
                if key in self.activities:
                    del self.activities[key]
                self.act_list.delete(s)
            self.update_status(f"Deleted {len(sel)} activities")

    def update_status(self, msg):
        self.status_bar.configure(text=msg)

    def show_error(self, msg):
        messagebox.showerror("Error", msg)


if __name__ == "__main__":
    app = GarminUltimateAnalyzer()
    app.mainloop()
