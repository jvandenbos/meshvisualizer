import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { NodeInfo } from '../types';

// Fix Leaflet default icon URLs
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

interface MapViewProps {
  nodes: Map<string, NodeInfo>;
}

export const MapView = ({ nodes }: MapViewProps) => {
  const withPos = Array.from(nodes.values()).filter(n => n.latitude && n.longitude);
  const center = withPos.length
    ? [withPos[0].latitude!, withPos[0].longitude!] as [number, number]
    : [49.2827, -123.1207] as [number, number];

  return (
    <MapContainer center={center} zoom={11} className="h-full w-full">
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {withPos.map(node => (
        <Marker key={node.id} position={[node.latitude!, node.longitude!] as [number, number]}>
          <Popup>
            <div className="text-sm">
              <div className="font-semibold">{node.long_name || node.short_name}</div>
              <div className="text-gray-500">{node.id}</div>
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
};

export default MapView;

