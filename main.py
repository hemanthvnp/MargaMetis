import logging
import time
import osmnx as ox

from route_optimizer.optimizer import RouteOptimizer
from route_optimizer.visualization.mapper import RouteVisualizer
from route_optimizer.utils.helpers import haversine_distance_m

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    try:
        from_place = input("Enter origin location (e.g., 'Gandhipuram, Coimbatore'): ").strip()
        to_place = input("Enter destination location (e.g., 'Prozone Mall, Coimbatore'): ").strip()

        if not from_place or not to_place:
            print("Origin and destination cannot be empty.")
            return

        logger.info("Converting locations to coordinates...")
        origin_coords = ox.geocode(from_place)
        dest_coords = ox.geocode(to_place)
        logger.info(f"Origin Coordinates: {origin_coords}")
        logger.info(f"Destination Coordinates: {dest_coords}")

        direct_dist = haversine_distance_m(*origin_coords, *dest_coords)
        graph_radius = max(int(direct_dist * 1.5), 3000)
        mid_point = ((origin_coords[0] + dest_coords[0]) / 2,
                     (origin_coords[1] + dest_coords[1]) / 2)

        optimizer = RouteOptimizer()
        optimizer.load_graph(center_point=mid_point, radius_m=graph_radius)

        logger.info("Calculating shortest route...")
        start_time = time.time()
        result = optimizer.find_shortest_route(origin_coords, dest_coords)
        duration = time.time() - start_time

        print("\n Route Found!")
        print(f"Total Distance: {result.distance_m / 1000:.2f} km")
        print(f"Calculation Time: {duration:.3f} seconds\n")
        RouteVisualizer.create_and_show_map(optimizer.graph, result, origin_coords, dest_coords)
    except Exception as e:
        logger.error("An error occurred during route calculation", exc_info=True)
        print(f"\n Could not find a route. Please check the locations or try again.")


if __name__ == "__main__":
    main()
