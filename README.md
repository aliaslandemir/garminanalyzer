
# **garminanalyzer**

![License](https://img.shields.io/github/license/aliaslandemir/garminanalyzer)
![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![GitHub stars](https://img.shields.io/github/stars/aliaslandemir/garminanalyzer?style=social)

## **Overview**

**garminanalyzer** is a Python-based **Garmin activity analysis tool** for `.tcx` files, providing **interactive visualizations**, **performance insights**, and **comparisons** in a modern GUI.

### **Key Features**
- 📊 **Advanced Data Analysis**: Heart Rate, Pace, Elevation, Training Load.
- 🗺️ **Interactive Route Mapping**: GPS visualization with **pace-based color overlays**.
- 🔄 **Multi-Activity Dashboard**: Compare up to **4 activities** side by side.
- 📂 **Data Storage & Management**: Save activities in an **SQLite database**.
- 📈 **Comparison Tools**: Side-by-side performance analysis.
- 📑 **Export PDF Reports**: Generate activity summaries.

---

## **Installation**

### **1️⃣ Clone the Repository**
```bash
git clone https://github.com/aliaslandemir/garminanalyzer.git
cd garminanalyzer
```

### **2️⃣ Create & Activate Virtual Environment**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### **3️⃣ Install Dependencies**
```bash
pip install -r requirements.txt
```

### **4️⃣ Run the Application**
```bash
python gui.py
```

---

## **Usage**

### **Loading Activities**
1. Click **"Open TCX"** to load `.tcx` files.
2. Activities appear in the **sidebar**.
3. Click an activity to **view graphs and stats**.

### **Route Visualization**
- Click **“Route Analysis”** to open an **interactive GPS map**.

### **Comparison Mode**
- Select **2 or 4 activities** and click **"Compare Activities"**.

### **Export Data**
- Click **"Export PDF"** to generate a summary report.

---

## **GUI Overview**

| Button         | Functionality |
|---------------|--------------|
| **Open TCX** | Load Garmin activities |
| **Export PDF** | Save activity summary |
| **Compare Activities** | Side-by-side analysis |
| **Training Load** | Track training trends |
| **Route Analysis** | View interactive GPS routes |

### **Tabs**
- **Dashboard** → Main activity insights.
- **Route Analysis** → GPS visualization.
- **Comparison** → Multi-activity metrics.

---

## **Project Structure**
```
📂 garminanalyzer/
│── 📂 src/                # Source Code
│   ├── advanced_tcx_parser.py
│   ├── activity_database.py
│   ├── advanced_visualizer.py
│── 📂 icons/              # GUI Icons
│── 📂 docs/               # Documentation
│── gui.py                 # Main Application
│── requirements.txt       # Dependencies
│── README.md              # Documentation
```

---

## **Contributing**
1. **Fork** the repository  
2. **Create a feature branch**  
3. **Submit a pull request (PR)**  

---

## **License**
This project is licensed under the **MIT License**.

---

## **Contact**
- GitHub: [@aliaslandemir](https://github.com/aliaslandemir)

**Enjoy using garminanalyzer? Leave a ⭐ on GitHub! 🚀**
```
