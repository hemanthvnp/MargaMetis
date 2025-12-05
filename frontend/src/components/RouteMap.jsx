import React from 'react';
import { MapContainer, TileLayer, Popup, Marker, Polyline } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for marker icons in react-leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

export const RouteMap = ({ origin, destination, pathCoordinates }) => {
  // Default center: India
  let center = [22.9734, 78.6569]; // India lat/lon
  let zoom = 5;

  // Convert path coordinates to leaflet format
  const polylinePoints = pathCoordinates?.map((coord) => [coord.lat, coord.lon]) || [];

  // If route exists, fit bounds to route
  const mapRef = React.useRef();
  React.useEffect(() => {
    if (mapRef.current && polylinePoints.length > 0) {
      const bounds = L.latLngBounds(polylinePoints);
      mapRef.current.fitBounds(bounds, { padding: [40, 40] });
    }
  }, [polylinePoints]);

  // If searching, center between origin and destination
  if (origin && destination) {
    center = [
      (origin.lat + destination.lat) / 2,
      (origin.lon + destination.lon) / 2,
    ];
    zoom = 12;
  }

  return (
    <div className="w-full h-full rounded-lg overflow-hidden shadow-lg">
      <MapContainer center={center} zoom={zoom} style={{ height: '100%', width: '100%' }} whenCreated={map => (mapRef.current = map)}>
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; OpenStreetMap contributors'
        />

        {/* Origin marker */}
        {origin && (
          <Marker position={[origin.lat, origin.lon]}>
            <Popup>
              <div className="font-semibold">{origin.name}</div>
              <div className="text-sm text-gray-600">Origin</div>
            </Popup>
          </Marker>
        )}

        {/* Destination marker */}
        {destination && (
          <Marker position={[destination.lat, destination.lon]}>
            <Popup>
              <div className="font-semibold">{destination.name}</div>
              <div className="text-sm text-gray-600">Destination</div>
            </Popup>
          </Marker>
        )}

        {/* Route polyline */}
        {polylinePoints.length > 0 && (
          <Polyline
            positions={polylinePoints}
            color="#3b82f6"
            weight={3}
            opacity={0.8}
          />
        )}
      </MapContainer>
    </div>
  );
};
