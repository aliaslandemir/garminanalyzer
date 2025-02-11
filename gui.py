#!/usr/bin/env python
"""
gui.py
------
A sleeker, modern CustomTkinter GUI for the advanced Garmin Running Analyzer.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, Menu
import customtkinter as ctk
import queue
import threading
import tempfile
import webbrowser
import os

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Local modules
from src.advanced_tcx_parser import AdvancedTcxParser
from src.activity_database import ActivityDatabase
from src.advanced_visualizer import AdvancedVisualizer

# Appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class GarminAdvancedAnalyzer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Professional Garmin Running Analyzer")
        self.geometry("1600x900")  # slightly smaller than 1920x1080 for convenience

        # Data structures
        self.activities = {}
        self.db = ActivityDatabase()
        self.parse_queue = queue.Queue()

        # Main UI creation
        self._create_menu()
        self._setup_ui()
        self._bind_events()

        # Periodically check parse queue
        self._poll_parse_queue()

    # ------------------------------------------------------
    # Menubar
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
    # Layout Setup
    # ------------------------------------------------------
    def _setup_ui(self):
        # Overall: two main columns
        #  - Left Column: sidebar for search + activity list
        #  - Right Column: tabbed interface (Dashboard / Route / Comparison)

        # A top-level frame to hold columns
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.pack(fill="both", expand=True)

        # Grid approach: left col is narrower, right col is the big area
        self.main_frame.columnconfigure(0, weight=0, minsize=300)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(0, weight=1)

        # LEFT SIDEBAR
        self.sidebar = ctk.CTkFrame(self.main_frame, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # RIGHT CONTENT
        self.content_frame = ctk.CTkFrame(self.main_frame, corner_radius=0)
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        # Build the sidebar (search + list)
        self._build_sidebar()

        # Build the tabbed interface
        self._build_tabs()

        # Status bar at bottom
        self._create_status_bar()

    def _build_sidebar(self):
        """
        Sidebar with a search box + list of loaded activities.
        """
        # A label or branding at the top
        heading_label = ctk.CTkLabel(
            self.sidebar,
            text="Activities",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        heading_label.pack(padx=10, pady=(10, 5))

        # Search entry
        self.search_entry = ctk.CTkEntry(
            self.sidebar, 
            placeholder_text="Search..."
        )
        self.search_entry.pack(fill="x", padx=10, pady=(0,10))

        # Activity list
        self.act_list = tk.Listbox(
            self.sidebar,
            selectmode=tk.EXTENDED,
            bg='#2b2b2b',
            fg='white',
            font=('TkDefaultFont', 11),
            height=25
        )
        self.act_list.pack(fill="both", expand=True, padx=10, pady=5)

        # Right-click menu on the list
        self.list_menu = tk.Menu(self.sidebar, tearoff=0)
        self.list_menu.add_command(label="Show Details", command=self.show_details)
        self.list_menu.add_command(label="Delete", command=self.delete_activity)

    def _build_tabs(self):
        """
        Create a tabbed interface on the right side with:
         - Dashboard
         - Route Analysis
         - Comparison
        """
        self.tabview = ctk.CTkTabview(self.content_frame, height=400, width=400)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.dashboard_tab = self.tabview.add("Dashboard")
        self.map_tab = self.tabview.add("Route Analysis")
        self.comp_tab = self.tabview.add("Comparison")

        # Initialize each tab's layout
        self._init_dashboard_tab()
        self._init_map_tab()
        self._init_comparison_tab()

    def _init_dashboard_tab(self):
        """
        Dashboard: top metrics + a frame for potential charts
        """
        # Top row: metrics
        metrics_frame = ctk.CTkFrame(self.dashboard_tab)
        metrics_frame.pack(fill="x", padx=10, pady=10)

        self.metrics = {
            'duration': self._create_metric_card(metrics_frame, "Duration", "--"),
            'distance': self._create_metric_card(metrics_frame, "Distance", "--"),
            'elevation': self._create_metric_card(metrics_frame, "Elevation", "--"),
            'calories': self._create_metric_card(metrics_frame, "Calories", "--")
        }

        # Plot area
        self.plot_frame = ctk.CTkFrame(self.dashboard_tab)
        self.plot_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def _init_map_tab(self):
        """
        Route analysis tab: pace colormap button
        """
        info_label = ctk.CTkLabel(
            self.map_tab,
            text="Generate a Folium Map with Pace-based color.\nSelect an activity on the left, then click below.",
            justify=tk.LEFT
        )
        info_label.pack(padx=10, pady=(10,5))

        show_route_button = ctk.CTkButton(
            self.map_tab,
            text="Show Route Analysis (Pace Colormap)",
            command=self.show_route_analysis
        )
        show_route_button.pack(pady=10)

    def _init_comparison_tab(self):
        """
        Basic placeholder for the 'Comparison' tab. 
        We'll display comparison results in a popup or in this tab if desired.
        """
        info_label = ctk.CTkLabel(
            self.comp_tab,
            text="Use 'Analysis → Compare Activities' from the menu.\nResults appear in a separate window.",
            justify=tk.LEFT
        )
        info_label.pack(padx=10, pady=10)

    def _create_metric_card(self, parent, title, value):
        frame = ctk.CTkFrame(parent, width=150, height=80)
        frame.pack_propagate(False)
        frame.pack(side=tk.LEFT, padx=5, pady=5)

        title_label = ctk.CTkLabel(frame, text=title, font=('Arial', 12))
        title_label.pack(pady=(5,0))

        value_label = ctk.CTkLabel(frame, text=value, font=('Arial', 18, 'bold'))
        value_label.pack(expand=True)

        return value_label

    def _create_status_bar(self):
        self.status_bar = ctk.CTkLabel(self, text="Ready", anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)

    # ------------------------------------------------------
    # Background Parsing
    # ------------------------------------------------------
    def _poll_parse_queue(self):
        while not self.parse_queue.empty():
            path, parser_or_error = self.parse_queue.get()
            if isinstance(parser_or_error, Exception):
                self.show_error(f"Error loading {os.path.basename(path)}: {parser_or_error}")
            else:
                activity_data = parser_or_error.activity_data
                self.db.save_activity(activity_data)
                self.activities[path] = activity_data
                self.act_list.insert(tk.END, os.path.basename(path))
                self.update_status(f"Loaded: {os.path.basename(path)}")
        self.after(200, self._poll_parse_queue)

    def load_tcx(self):
        files = filedialog.askopenfilenames(filetypes=[("TCX Files", "*.tcx")])
        if not files:
            return

        def parse_file(path):
            try:
                parser = AdvancedTcxParser(path)
                self.parse_queue.put((path, parser))
            except Exception as e:
                self.parse_queue.put((path, e))

        for path in files:
            thread = threading.Thread(target=parse_file, args=(path,), daemon=True)
            thread.start()

    # ------------------------------------------------------
    # Right-Click Menu Handling
    # ------------------------------------------------------
    def show_list_menu(self, event):
        widget = event.widget
        index = widget.nearest(event.y)
        if 0 <= index < len(self.act_list.get(0, tk.END)):
            self.act_list.selection_clear(0, tk.END)
            self.act_list.selection_set(index)
        try:
            self.list_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.list_menu.grab_release()

    # ------------------------------------------------------
    # Event Bindings
    # ------------------------------------------------------
    def _bind_events(self):
        self.act_list.bind('<<ListboxSelect>>', self.on_activity_select)
        self.act_list.bind("<Button-3>", self.show_list_menu)
        self.search_entry.bind("<KeyRelease>", self.filter_activities)

    def on_activity_select(self, event):
        selected = self.act_list.curselection()
        if not selected:
            return
        if len(selected) == 1:
            self.show_single_activity()
        else:
            self.show_comparison()

    # ------------------------------------------------------
    # Core Functionalities
    # ------------------------------------------------------
    def show_single_activity(self):
        selected = self.act_list.curselection()
        if not selected:
            return

        path = list(self.activities.keys())[selected[0]]
        activity = self.activities[path]
        laps = activity['laps']

        total_duration = sum(l.get('total_time', 0) or 0 for l in laps)
        total_distance = sum(l.get('distance', 0) or 0 for l in laps)
        total_calories = sum(l.get('calories', 0) or 0 for l in laps)
        elev_gain = activity['extended_stats'].get('elevation_gain', 0)

        self.metrics['duration'].configure(text=f"{round(total_duration, 2)} s")
        self.metrics['distance'].configure(text=f"{round(total_distance, 2)} m")
        self.metrics['elevation'].configure(text=f"{round(elev_gain, 2)} m")
        self.metrics['calories'].configure(text=str(total_calories))

        # Clear old charts in dashboard
        for widget in self.plot_frame.winfo_children():
            widget.destroy()

        # 1) Main multi-trace dashboard
        fig = AdvancedVisualizer.create_interactive_dashboard(activity)
        # 2) Optional distribution histogram
        fig_dist = AdvancedVisualizer.create_distribution_plots(activity)

        if fig:
            html_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
            fig.write_html(html_file.name)
            webbrowser.open_new_tab(f"file://{html_file.name}")

        if fig_dist:
            html_file2 = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
            fig_dist.write_html(html_file2.name)
            webbrowser.open_new_tab(f"file://{html_file2.name}")

    def show_details(self):
        selected = self.act_list.curselection()
        if not selected:
            return
        activity_key = list(self.activities.keys())[selected[0]]
        activity = self.activities[activity_key]

        laps = activity['laps']
        durations = [lap.get('total_time', 0) for lap in laps]
        total_duration = sum(durations) if durations else 0
        distances = [lap.get('distance', 0) for lap in laps]
        total_distance = sum(distances) if distances else 0
        cals = [lap.get('calories', 0) for lap in laps]
        total_calories = sum(cals) if cals else 0

        # A small popup window
        detail_window = ctk.CTkToplevel(self)
        detail_window.title("Activity Details")
        detail_window.geometry("500x400")

        text = f"""
Sport: {activity['metadata']['sport']}
Start Time: {activity['metadata']['start_time']}
Duration (s): {round(total_duration,2)}
Distance (m): {round(total_distance,2)}
Calories: {total_calories}
VO2 Max: {activity['metadata']['training'].get('vo2_max', 'N/A')}
Training Effect: {activity['metadata']['training'].get('training_effect', 'N/A')}

Extended Stats:
{activity['extended_stats']}
"""
        info_label = ctk.CTkLabel(detail_window, text=text, justify="left")
        info_label.pack(fill="both", expand=True, padx=20, pady=20)

    def show_route_analysis(self):
        selected = self.act_list.curselection()
        if not selected:
            messagebox.showwarning("No Activity Selected", "Please select an activity first.")
            return
        path = list(self.activities.keys())[selected[0]]
        activity = self.activities[path]

        route_map = AdvancedVisualizer.create_route_map(activity)
        if route_map is None:
            self.show_error("No valid lat/long data found for route.")
            return

        temp_html = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
        route_map.save(temp_html.name)
        webbrowser.open_new_tab(f"file://{temp_html.name}")

    def show_comparison(self):
        selected = self.act_list.curselection()
        if len(selected) < 2:
            messagebox.showwarning("Selection Error", "Select at least 2 activities to compare")
            return

        comparison_window = ctk.CTkToplevel(self)
        comparison_window.title("Activity Comparison")
        comparison_window.geometry("500x400")

        text = ""
        for idx in selected:
            key = list(self.activities.keys())[idx]
            data = self.activities[key]
            name = os.path.basename(key)

            laps = data['laps']
            total_time = sum(l.get('total_time', 0) for l in laps)
            total_dist = sum(l.get('distance', 0) for l in laps)
            text += f"{name}: Duration={round(total_time,2)}s  Distance={round(total_dist,2)}m\n"

        ctk.CTkLabel(comparison_window, text=text, justify="left").pack(padx=20, pady=20, fill="both", expand=True)

    def export_pdf(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")]
        )
        if not file_path:
            return
        try:
            c = canvas.Canvas(file_path, pagesize=letter)
            c.setFont("Helvetica", 12)

            selected = self.act_list.curselection()
            if selected:
                activity_key = list(self.activities.keys())[selected[0]]
                activity = self.activities[activity_key]

                laps = activity['laps']
                total_duration = sum(l.get('total_time', 0) for l in laps)
                total_distance = sum(l.get('distance', 0) for l in laps)

                c.drawString(100, 750, f"Activity Report: {activity['metadata']['sport']}")
                c.drawString(100, 730, f"Date: {activity['metadata']['start_time']}")
                c.drawString(100, 710, f"Duration: {round(total_duration,2)}s")
                c.drawString(100, 690, f"Distance: {round(total_distance,2)}m")
                c.drawString(100, 670, f"Extended Stats: {activity['extended_stats']}")

            c.save()
            self.update_status(f"Exported PDF to {file_path}")
        except Exception as e:
            self.show_error(f"PDF Export Error: {str(e)}")

    def show_training_load(self):
        if not self.activities:
            messagebox.showwarning("No Data", "Load activities first")
            return

        import plotly.graph_objects as go
        fig = go.Figure()
        for path, data in self.activities.items():
            start_time = data['metadata'].get('start_time', None)
            training_load = data['extended_stats'].get('training_load', None)
            if start_time and training_load is not None:
                fig.add_trace(go.Scatter(
                    x=[start_time], y=[training_load],
                    name=os.path.basename(path),
                    mode='markers+text',
                    text=[os.path.basename(path)],
                    textposition="top center"
                ))
        fig.update_layout(title="Training Load Comparison", template='plotly_dark')
        fig.show()

    def delete_activity(self):
        selected = self.act_list.curselection()
        if not selected:
            return
        confirm = messagebox.askyesno("Confirm Delete", "Are you sure you want to delete these activities?")
        if confirm:
            for idx in reversed(selected):
                key = list(self.activities.keys())[idx]
                if key in self.activities:
                    del self.activities[key]
                self.act_list.delete(idx)
            self.update_status(f"Deleted {len(selected)} activities")

    def filter_activities(self, event=None):
        search_term = self.search_entry.get().lower()
        self.act_list.delete(0, tk.END)
        for path in self.activities.keys():
            fname = os.path.basename(path).lower()
            if search_term in fname:
                self.act_list.insert(tk.END, os.path.basename(path))

    # ------------------------------------------------------
    # Helpers
    # ------------------------------------------------------
    def update_status(self, message):
        self.status_bar.configure(text=message)

    def show_error(self, message):
        messagebox.showerror("Error", message)

# ----------------------------------------
# Entry point
# ----------------------------------------
if __name__ == "__main__":
    app = GarminAdvancedAnalyzer()
    app.mainloop()
