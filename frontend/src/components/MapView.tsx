import React, { useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle, Polyline } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.heat';
import { NodeInfo } from '../types';
import { Battery, Signal, Router, Activity } from 'lucide-react';

// Fix Leaflet icon issues
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

interface MapViewProps {
  nodes: Map<string, NodeInfo>;
  localNodeId?: string;
  selectedNode: string | null;
  onNodeSelect: (nodeId: string | null) => void;
}

// Calculate signal strength color
const getSignalColor = (rssi: number | null | undefined): string => {
  if (!rssi) return '#6b7280'; // gray
  if (rssi > -75) return '#10b981'; // green
  if (rssi > -85) return '#eab308'; // yellow
  if (rssi > -95) return '#f97316'; // orange
  return '#ef4444'; // red
};

// Create custom icon for nodes
const createNodeIcon = (node: NodeInfo, isLocal: boolean, isSelected: boolean) => {
  const color = isLocal ? '#10b981' : 
                node.role === 'ROUTER' ? '#a855f7' : 
                '#3b82f6';
  
  const size = isLocal ? 30 : 
               node.hop_count === 1 ? 25 :
               node.hop_count === 2 ? 20 : 15;
  
  return L.divIcon({
    className: 'custom-node-marker',
    html: `
      <div style="
        width: ${size}px;
        height: ${size}px;
        background: ${color};
        border: 3px solid ${isSelected ? '#fbbf24' : '#ffffff'};
        border-radius: ${node.role === 'ROUTER' ? '0%' : '50%'};
        transform: ${node.role === 'ROUTER' ? 'rotate(45deg)' : 'none'};
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 10px;
        color: white;
        font-weight: bold;
      ">
        ${node.short_name.slice(0, 2).toUpperCase()}
      </div>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
};

// Calculate signal propagation based on RSSI and free space path loss
const calculateCoverageRadius = (rssi: number | null | undefined): number => {
  if (!rssi) return 100; // Default 100m radius
  
  // Simplified free space path loss calculation
  // Assuming 915MHz, typical Meshtastic power levels
  const maxRange = 5000; // 5km max theoretical range
  const minRSSI = -130;   // Minimum receivable signal
  const maxRSSI = -50;    // Maximum signal strength
  
  const normalized = (rssi - minRSSI) / (maxRSSI - minRSSI);
  return maxRange * Math.pow(normalized, 2); // Quadratic falloff
};

export const MapView: React.FC<MapViewProps> = ({
  nodes,
  localNodeId,
  selectedNode,
  onNodeSelect,
}) => {
  const mapRef = useRef<L.Map | null>(null);
  const heatmapRef = useRef<any>(null);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [showConnections, setShowConnections] = useState(true);
  const [mapReady, setMapReady] = useState(false);
  
  // Get center coordinates from nodes with positions
  const getMapCenter = (): [number, number] => {
    const nodesWithPosition = Array.from(nodes.values()).filter(
      n => n.latitude && n.longitude
    );
    
    if (nodesWithPosition.length === 0) {
      // Default to Vancouver area if no positions
      return [49.2827, -123.1207];
    }
    
    const avgLat = nodesWithPosition.reduce((sum, n) => sum + (n.latitude || 0), 0) / nodesWithPosition.length;
    const avgLon = nodesWithPosition.reduce((sum, n) => sum + (n.longitude || 0), 0) / nodesWithPosition.length;
    return [avgLat, avgLon];
  };

  // Update heatmap when nodes change
  useEffect(() => {
    if (!mapRef.current || !mapReady || !showHeatmap) return;

    // Remove old heatmap
    if (heatmapRef.current) {
      mapRef.current.removeLayer(heatmapRef.current);
    }

    // Create heatmap data points
    const heatPoints: [number, number, number][] = [];
    
    nodes.forEach(node => {
      if (node.latitude && node.longitude) {
        // Weight based on signal strength and node type
        let intensity = 0.5;
        
        if (node.rssi) {
          intensity = Math.max(0.1, (node.rssi + 130) / 80); // Normalize RSSI to 0-1
        }
        
        if (node.role === 'ROUTER') {
          intensity *= 1.5; // Routers have stronger coverage
        }
        
        heatPoints.push([node.latitude, node.longitude, intensity]);
      }
    });

    if (heatPoints.length > 0) {
      // Create heatmap layer
      heatmapRef.current = (L as any).heatLayer(heatPoints, {
        radius: 50,
        blur: 30,
        maxZoom: 10,
        gradient: {
          0.0: '#3b82f6',
          0.2: '#10b981',
          0.4: '#eab308',
          0.6: '#f97316',
          0.8: '#ef4444',
          1.0: '#dc2626'
        }
      }).addTo(mapRef.current);
    }
  }, [nodes, mapReady, showHeatmap]);

  // Calculate connections between nodes
  const getConnections = () => {
    const connections: Array<{
      from: NodeInfo;
      to: NodeInfo;
      quality: number;
    }> = [];

    // Simple approach: connect nodes within range based on RSSI
    const nodeArray = Array.from(nodes.values());
    
    nodeArray.forEach((node1, i) => {
      if (!node1.latitude || !node1.longitude) return;
      
      nodeArray.slice(i + 1).forEach(node2 => {
        if (!node2.latitude || !node2.longitude) return;
        
        // Calculate distance
        const distance = L.latLng(node1.latitude, node1.longitude)
          .distanceTo(L.latLng(node2.latitude, node2.longitude));
        
        // Estimate connection quality based on distance and RSSI
        const maxRange = 5000; // 5km max range
        if (distance < maxRange) {
          const quality = Math.max(0, 1 - (distance / maxRange));
          connections.push({ from: node1, to: node2, quality });
        }
      });
    });

    return connections;
  };

  return (
    <div className="relative h-full w-full">
      {/* Control Panel */}
      <div className="absolute top-4 right-4 z-[1000] bg-gray-800 rounded-lg p-3 space-y-2">
        <label className="flex items-center space-x-2 text-sm text-gray-300">
          <input
            type="checkbox"
            checked={showHeatmap}
            onChange={(e) => setShowHeatmap(e.target.checked)}
            className="rounded"
          />
          <span>Signal Heatmap</span>
        </label>
        <label className="flex items-center space-x-2 text-sm text-gray-300">
          <input
            type="checkbox"
            checked={showConnections}
            onChange={(e) => setShowConnections(e.target.checked)}
            className="rounded"
          />
          <span>Connections</span>
        </label>
      </div>

      {/* Map Container */}
      <MapContainer
        center={getMapCenter()}
        zoom={11}
        className="h-full w-full"
        ref={(map) => {
          if (map) {
            mapRef.current = map;
            setMapReady(true);
          }
        }}
      >
        {/* Base Map Tiles */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          opacity={0.7}
        />

        {/* Dark overlay for better contrast */}
        <TileLayer
          url="https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png"
          opacity={0.3}
        />

        {/* Signal coverage circles */}
        {Array.from(nodes.values()).map(node => {
          if (!node.latitude || !node.longitude) return null;
          
          const radius = calculateCoverageRadius(node.rssi);
          const color = getSignalColor(node.rssi);
          
          return (
            <Circle
              key={`coverage-${node.id}`}
              center={[node.latitude, node.longitude]}
              radius={radius}
              pathOptions={{
                color: color,
                fillColor: color,
                fillOpacity: 0.1,
                weight: 1,
                opacity: 0.3,
              }}
            />
          );
        })}

        {/* Connection lines */}
        {showConnections && getConnections().map((conn, idx) => (
          <Polyline
            key={`conn-${idx}`}
            positions={[
              [conn.from.latitude!, conn.from.longitude!],
              [conn.to.latitude!, conn.to.longitude!],
            ]}
            pathOptions={{
              color: conn.quality > 0.7 ? '#10b981' : 
                     conn.quality > 0.4 ? '#eab308' : '#ef4444',
              weight: Math.max(1, conn.quality * 3),
              opacity: conn.quality * 0.5,
              dashArray: conn.quality < 0.5 ? '5, 10' : undefined,
            }}
          />
        ))}

        {/* Node markers */}
        {Array.from(nodes.values()).map(node => {
          if (!node.latitude || !node.longitude) return null;
          
          const isLocal = node.id === localNodeId;
          const isSelected = node.id === selectedNode;
          
          return (
            <Marker
              key={node.id}
              position={[node.latitude, node.longitude]}
              icon={createNodeIcon(node, isLocal, isSelected)}
              eventHandlers={{
                click: () => onNodeSelect(node.id),
              }}
            >
              <Popup>
                <div className="p-2 min-w-[200px]">
                  <h3 className="font-bold text-lg mb-2">
                    {node.long_name || node.short_name}
                  </h3>
                  <div className="space-y-1 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="text-gray-500">ID:</span>
                      <span className="font-mono">{node.id}</span>
                    </div>
                    {node.role && (
                      <div className="flex items-center gap-2">
                        <Router className="h-3 w-3" />
                        <span>{node.role}</span>
                      </div>
                    )}
                    {node.battery_level !== null && (
                      <div className="flex items-center gap-2">
                        <Battery className="h-3 w-3" />
                        <span>{node.battery_level}%</span>
                      </div>
                    )}
                    {node.rssi !== null && (
                      <div className="flex items-center gap-2">
                        <Signal className="h-3 w-3" />
                        <span>{node.rssi} dBm / {node.snr?.toFixed(1)} dB</span>
                      </div>
                    )}
                    <div className="flex items-center gap-2">
                      <Activity className="h-3 w-3" />
                      <span>Hops: {node.hop_count || 'Direct'}</span>
                    </div>
                    <div className="text-xs text-gray-500 mt-2">
                      Coverage: ~{calculateCoverageRadius(node.rssi).toFixed(0)}m
                    </div>
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 z-[1000] bg-gray-800 rounded-lg p-3">
        <h4 className="text-sm font-semibold text-gray-300 mb-2">Signal Strength</h4>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span className="text-xs text-gray-400">Excellent (&gt;-75 dBm)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
            <span className="text-xs text-gray-400">Good (-75 to -85)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-orange-500"></div>
            <span className="text-xs text-gray-400">Weak (-85 to -95)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <span className="text-xs text-gray-400">Poor (&lt;-95)</span>
          </div>
        </div>
      </div>
    </div>
  );
};