import os
import logging
import folium
import tempfile
import webbrowser
import networkx as nx
from ..core.pathfinder import RouteResult

logger = logging.getLogger(__name__)

class RouteVisualizer(object):
    @staticmethod
    def create_and_show_map(graph, result, origin_coords, dest_coords):
        logger.info("Generating map...")
        route_coords = [(graph.nodes[n]['y'], graph.nodes[n]['x']) for n in result.path]
        mid_lat = sum(lat for lat, lon in route_coords) / len(route_coords)
        mid_lon = sum(lon for lat, lon in route_coords) / len(route_coords)
        route_map = folium.Map(location=(mid_lat, mid_lon), zoom_start=14, tiles='OpenStreetMap')

        folium.PolyLine(
            locations=route_coords,
            color='blue',
            weight=5
        ).add_to(route_map)

        popup_text = "Distance: {:.2f} km".format(result.distance_m / 1000.0)
        folium.Marker(
            location=origin_coords,
            popup="Start",
            icon=folium.Icon(color='green')
        ).add_to(route_map)

        folium.Marker(
            location=dest_coords,
            popup="Destination<br>{}".format(popup_text),
            icon=folium.Icon(color='red')
        ).add_to(route_map)

        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
        try:
            route_map.save(tmp_file.name)
            abs_path = os.path.abspath(tmp_file.name)
            webbrowser.open("file://{}".format(abs_path))
            logger.info("Map opened in browser: {}".format(abs_path))
        finally:
            tmp_file.close()
