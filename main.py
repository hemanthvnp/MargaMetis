import logging
import time
from typing import Tuple

import osmnx as ox

from route_optimizer.optimizer import RouteOptimizer
from route_optimizer.visualization.mapper import RouteVisualizer
from route_optimizer.utils.helpers import haversine_distance_m

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_location_input(prompt: str) -> str:
    """
    Prompt the user for a location and ensure it's not empty.

    Args:
        prompt (str): The message to display to the user.

    Returns:
        str: User-provided location.
    """
    location = input(prompt).strip()
    if not location:
        raise ValueError("Location cannot be empty.")
    return location


def main() -> None:
    """
    Main function to calculate and visualize the shortest route between two locations.
    """
    try:
        from_place = get_location_input("Enter origin location (e.g., 'Gandhipuram, Coimbatore'): ")
        to_place = get_location_input("Enter destination location (e.g., 'Prozone Mall, Coimbatore'): ")

        logger.info("Converting locations to coordinates...")
        origin_coords: Tuple[float, float] = ox.geocode(from_place)
        dest_coords: Tuple[float, float] = ox.geocode(to_place)
        logger.info(f"Origin Coordinates: {origin_coords}")
        logger.info(f"Destination Coordinates: {dest_coords}")

        # Estimate graph radius
        direct_dist = haversine_distance_m(*origin_coords, *dest_coords)
        graph_radius = max(int(direct_dist * 1.5), 3000)  # Ensure minimum radius of 3 km
        mid_point = ((origin_coords[0] + dest_coords[0]) / 2,
                     (origin_coords[1] + dest_coords[1]) / 2)

        # Load graph and calculate shortest path
        optimizer = RouteOptimizer()
        optimizer.load_graph(center_point=mid_point, radius_m=graph_radius)

        logger.info("Calculating shortest route...")
        start_time = time.time()
        result = optimizer.find_shortest_route(origin_coords, dest_coords)
        duration = time.time() - start_time

        print("\nRoute Found!")
        print(f"Total Distance: {result.distance_m / 1000:.2f} km")
        print(f"Calculation Time: {duration:.3f} seconds\n")

        # Visualize the route
        RouteVisualizer.create_and_show_map(optimizer.graph, result, origin_coords, dest_coords)

    except ValueError as ve:
        logger.warning(f"Invalid input: {ve}")
        print(f"\nError: {ve}")
    except Exception as e:
        logger.error("An error occurred during route calculation", exc_info=True)
        print("\nCould not find a route. Please check the locations or try again.")


if __name__ == "__main__":
    main()
