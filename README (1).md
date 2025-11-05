# MārgaMetis 🚗🗺️
**Intelligent Route Optimization System using A\* Algorithm**

---

## 📘 Overview
**MārgaMetis** is a route optimization system designed to find the most efficient paths using the **A\*** algorithm with the **Haversine formula** as a heuristic for real-world accuracy.  
It dynamically considers **distance**, **traffic**, and **fuel efficiency** to provide multiple optimized route options suitable for **logistics**, **travel**, and **fleet management**.

---

## 🧠 Key Features
- 🚦 **A\* Pathfinding Algorithm** with **Haversine heuristic**  
- 🌍 **OSMnx** for real-world map data extraction  
- 🗺️ **Folium** for interactive map visualization  
- ⛽ Route optimization based on **distance**, **traffic**, and **fuel efficiency**  
- 🧭 Multiple route suggestions for flexible decision-making  

---

## 🛠️ Tech Stack
- **Language:** Python  
- **Algorithms:** A\* Search with Haversine heuristic  
- **Libraries:**  
  - [OSMnx](https://github.com/gboeing/osmnx) – for map graph data  
  - [Folium](https://python-visualization.github.io/folium/) – for route visualization  
  - [NetworkX](https://networkx.org/) – for graph representation and pathfinding  

---

## ⚙️ Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/MargaMetis.git
cd MargaMetis

# Create virtual environment
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## 🚀 Usage

```bash
# Run the main script
python main.py
```

You can modify the **source** and **destination** locations within `main.py`.  
The optimized routes will be displayed interactively in your browser using **Folium**.

---

## 📈 Example Output
- Displays optimal and alternate routes on an interactive map.
- Shows distance, estimated time, and efficiency metrics.

---

## 🧩 Project Structure
```
MargaMetis/
├── main.py                 # Main application entry point
├── route_optimizer.py      # Core A* and heuristic logic
├── map_visualizer.py       # Folium-based visualization
├── data_utils.py           # Map and traffic data handling
├── requirements.txt        # Dependencies
└── README.md               # Project documentation
```

---

## 🤝 Contributing
Pull requests are welcome! Feel free to suggest improvements or report issues via the **Issues** tab.

---

## 🧑‍💻 Author
**Hemanth Vasudev N P**  
M.Sc. Software Systems, PSG Tech  
[GitHub](https://github.com/hemanthvnp)

---

## 🪪 License
This project is licensed under the **MIT License** – see the LICENSE file for details.
