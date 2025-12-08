from flask import Blueprint, request, jsonify, session
import logging
import time
from typing import Tuple

import osmnx as ox

from route_optimizer.optimizer import RouteOptimizer
from route_optimizer.utils.helpers import haversine_distance_m
from app.models import db, User, SearchHistory

logger = logging.getLogger(__name__)
route_bp = Blueprint('routes', __name__)

# Global optimizer instance
optimizer = None


def get_optimizer():
    """Get or create optimizer instance."""
    global optimizer
    if optimizer is None:
        optimizer = RouteOptimizer()
    return optimizer


@route_bp.route('/route/calculate', methods=['POST'])
def calculate_route():
    """
    Calculate shortest route between two locations.
    
    Request JSON:
    {
        "origin": "Location name or coords",
        "destination": "Location name or coords",
        "origin_coords": [lat, lon] (optional),
        "dest_coords": [lat, lon] (optional)
    }
    
    Returns:
        JSON with route details including path, distance, and coordinates
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        origin = data.get('origin', '').strip()
        destination = data.get('destination', '').strip()
        origin_coords = data.get('origin_coords')
        dest_coords = data.get('dest_coords')
        route_type = data.get('route_type', 'shortest')
        time_of_day = int(data.get('time_of_day', 17))
        vehicle_type = data.get('vehicle_type', 'car')
        
        # Validate inputs
        if not origin or not destination:
            return jsonify({'error': 'Origin and destination are required'}), 400
        
        logger.info(f"Route request: {origin} -> {destination}")
        
        try:
            # Geocode locations if coordinates not provided
            if not origin_coords:
                origin_coords = ox.geocode(origin)
            else:
                origin_coords = tuple(origin_coords)
                
            if not dest_coords:
                dest_coords = ox.geocode(destination)
            else:
                dest_coords = tuple(dest_coords)
            
            logger.info(f"Origin coordinates: {origin_coords}")
            logger.info(f"Destination coordinates: {dest_coords}")
            
            # Estimate graph radius
            direct_dist = haversine_distance_m(*origin_coords, *dest_coords)
            graph_radius = max(int(direct_dist * 1.5), 3000)
            mid_point = (
                (origin_coords[0] + dest_coords[0]) / 2,
                (origin_coords[1] + dest_coords[1]) / 2
            )
            
            # Load graph and calculate route
            optimizer_instance = get_optimizer()
            logger.info("Loading graph...")
            optimizer_instance.load_graph(center_point=mid_point, radius_m=graph_radius)

            logger.info(f"Calculating {route_type} route...")
            start_time = time.time()
            result = optimizer_instance.find_route(origin_coords, dest_coords, route_type, time_of_day, vehicle_type)
            duration = time.time() - start_time

            # Get node coordinates for the path
            path_coords = []
            for node in result["path"]:
                node_data = optimizer_instance.graph.nodes[node]
                path_coords.append({
                    'lat': node_data['y'],
                    'lon': node_data['x']
                })

            response_payload = {
                'success': True,
                'distance_km': round(result["distance_m"] / 1000, 2),
                'distance_m': round(result["distance_m"], 2),
                'calculation_time_s': round(duration, 3),
                'path_nodes': len(result["path"]),
                'origin': {
                    'name': origin,
                    'lat': origin_coords[0],
                    'lon': origin_coords[1]
                },
                'destination': {
                    'name': destination,
                    'lat': dest_coords[0],
                    'lon': dest_coords[1]
                },
                'path_coordinates': path_coords,
                'traffic_prediction': result["traffic"],
                'estimated_time_min': result["estimated_time_min"],
                'best_hour': result["best_hour"],
                'best_time_min': result["best_time_min"],
                'route_type': route_type,
                'vehicle_type': vehicle_type
            }

            # Log search into database
            try:
                username = session.get('username')
                user_id = None
                if username:
                    user = User.query.filter_by(username=username).first()
                    if user:
                        user_id = user.id
                record = SearchHistory(
                    user_id=user_id,
                    origin=origin,
                    destination=destination,
                    route_type=route_type,
                    vehicle_type=vehicle_type,
                    distance_m=response_payload['distance_m'],
                    estimated_time_min=response_payload.get('estimated_time_min'),
                    result_json=response_payload
                )
                db.session.add(record)
                db.session.commit()
            except Exception as log_err:
                logger.warning(f"Failed to log search history: {log_err}")

            return jsonify(response_payload), 200
            
        except Exception as e:
            logger.error(f"Error during route calculation: {str(e)}", exc_info=True)
            return jsonify({
                'error': 'Could not find a route. Please check the locations.',
                'details': str(e)
            }), 400
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred'}), 500


@route_bp.route('/route/geocode', methods=['POST'])
def geocode_location():
    """
    Geocode a location name to coordinates.
    
    Request JSON:
    {
        "location": "Location name"
    }
    
    Returns:
        JSON with latitude and longitude
    """
    try:
        data = request.get_json()
        location = data.get('location', '').strip()
        
        if not location:
            return jsonify({'error': 'Location is required'}), 400
        
        logger.info(f"Geocoding: {location}")
        
        try:
            coords = ox.geocode(location)
            return jsonify({
                'success': True,
                'location': location,
                'lat': coords[0],
                'lon': coords[1]
            }), 200
        except Exception as e:
            logger.warning(f"Geocoding failed for {location}: {str(e)}")
            return jsonify({'error': f'Could not find location: {location}'}), 404
    
    except Exception as e:
        logger.error(f"Geocoding error: {str(e)}", exc_info=True)
        return jsonify({'error': 'An error occurred during geocoding'}), 500
