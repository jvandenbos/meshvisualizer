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
  localNodeId?: string | null;
}

const createNodeIcon = (node: NodeInfo, isLocal: boolean) => {
  const color = isLocal ? '#10b981' : '#3b82f6';
  const size = isLocal ? 28 : (node.hop_count === 1 ? 24 : 20);
  const badge = node.hop_count === 0 ? 'L' : (node.hop_count === 1 ? 'D' : (node.hop_count && node.hop_count < 999 ? String(node.hop_count) : '')); 
  const badgeHtml = badge ? `<div style="position:absolute;top:-6px;right:-6px;background:#111827;border:1px solid #374151;color:#f3f4f6;font-size:10px;line-height:1;padding:2px 4px;border-radius:8px;">${badge}</div>` : '';
  return L.divIcon({
    className: 'custom-node-marker',
    html: `
      <div style="position:relative;width:${size}px;height:${size}px;background:${color};border:2px solid #fff;border-radius:50%;box-shadow:0 2px 8px rgba(0,0,0,0.3);"></div>
      ${badgeHtml}
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
};

export const MapView = ({ nodes, localNodeId }: MapViewProps) => {
  const withPos = Array.from(nodes.values()).filter(
    n => n.latitude !== undefined && n.latitude !== null && n.longitude !== undefined && n.longitude !== null
  );
  const center = (() => {
    if (withPos.length === 0) return [49.2827, -123.1207] as [number, number];
    const avgLat = withPos.reduce((sum, n) => sum + (n.latitude || 0), 0) / withPos.length;
    const avgLon = withPos.reduce((sum, n) => sum + (n.longitude || 0), 0) / withPos.length;
    return [avgLat, avgLon] as [number, number];
  })();

  return (
    <MapContainer center={center} zoom={11} className="h-full w-full">
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {clusterize(withPos).map((item) => {
        if (item.type === 'cluster') {
          const { lat, lon, count } = item;
          const clusterIcon = L.divIcon({
            className: 'custom-cluster',
            html: `<div style="display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:#4b5563;color:#fff;border:2px solid #e5e7eb;box-shadow:0 2px 6px rgba(0,0,0,0.3);font-size:12px;">${count}</div>`,
            iconSize: [28, 28],
            iconAnchor: [14, 14]
          });
          return (
            <Marker key={`cluster-${lat}-${lon}-${count}`} position={[lat, lon]} icon={clusterIcon} />
          );
        } else {
          const node = item.node;
          return (
            <Marker
              key={node.id}
              position={[node.latitude!, node.longitude!] as [number, number]}
              icon={createNodeIcon(node, node.id === localNodeId)}
            >
              <Popup>
                <div className="text-sm">
                  <div className="font-semibold">{node.long_name || node.short_name}</div>
                  <div className="text-gray-500">{node.id}</div>
                  <div className="text-xs text-gray-400 mt-1">
                    {node.latitude?.toFixed(5)}, {node.longitude?.toFixed(5)}
                    {node.altitude !== undefined && node.altitude !== null ? ` • ${node.altitude} m` : ''}
                  </div>
                  {node.hop_count !== undefined && (
                    <div className="text-xs text-gray-400 mt-1">Hops: {node.hop_count === 0 ? 'LOCAL' : (node.hop_count === 1 ? 'DIRECT' : node.hop_count)}</div>
                  )}
                </div>
              </Popup>
            </Marker>
          );
        }
      })}
    </MapContainer>
  );
};

export default MapView;

function clusterize(nodes: NodeInfo[]): Array<
  | { type: 'cluster'; lat: number; lon: number; count: number }
  | { type: 'single'; node: NodeInfo }
> {
  const bucketSize = 0.01; // ~1.1 km
  const buckets = new Map<string, NodeInfo[]>();
  for (const n of nodes) {
    const key = `${Math.round((n.latitude || 0) / bucketSize) * bucketSize}|${Math.round((n.longitude || 0) / bucketSize) * bucketSize}`;
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key)!.push(n);
  }
  const out: Array<{ type: 'cluster'; lat: number; lon: number; count: number } | { type: 'single'; node: NodeInfo }> = [];
  for (const [_, group] of buckets.entries()) {
    if (group.length === 1) {
      out.push({ type: 'single', node: group[0] });
    } else {
      const lat = group.reduce((s, n) => s + (n.latitude || 0), 0) / group.length;
      const lon = group.reduce((s, n) => s + (n.longitude || 0), 0) / group.length;
      out.push({ type: 'cluster', lat, lon, count: group.length });
    }
  }
  return out;
}
