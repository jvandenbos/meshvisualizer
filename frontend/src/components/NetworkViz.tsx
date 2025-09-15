import { useMemo, useRef, useEffect, useState, useCallback } from 'react';
import type { NodeInfo, NetworkLink } from '../types';

interface NetworkVizProps {
  nodes: NodeInfo[];
  links: NetworkLink[];
  localNodeId?: string | null;
}

type Point = { x: number; y: number };

export const NetworkViz = ({ nodes, links, localNodeId }: NetworkVizProps) => {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [size, setSize] = useState<{ w: number; h: number }>({ w: 800, h: 420 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Resize observer
  useEffect(() => {
    const el = svgRef.current?.parentElement;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const rect = el.getBoundingClientRect();
      setSize({ w: Math.max(320, rect.width), h: Math.max(200, rect.height) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (rect) {
      setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    }
  }, []);

  const nodeMap = useMemo(() => {
    const map = new Map<string, NodeInfo>();
    for (const n of nodes) map.set(n.id, n);
    return map;
  }, [nodes]);

  const filteredLinks = useMemo(() => {
    return links.filter(l => nodeMap.has(l.from_id) && nodeMap.has(l.to_id));
  }, [links, nodeMap]);

  // Improved radial layout with better spacing
  const layout = useMemo(() => {
    const center: Point = { x: size.w / 2, y: size.h / 2 };
    const myId = localNodeId || '';
    const local = nodes.find(n => n.id === myId);
    const groups: Record<string, NodeInfo[]> = { local: [], h0: [], h1: [], h2: [], h3: [], hx: [] };

    for (const n of nodes) {
      if (n.id === myId) groups.local.push(n);
      else if ((n.hop_count ?? 999) === 0) groups.h0.push(n);
      else if ((n.hop_count ?? 999) === 1) groups.h1.push(n);
      else if ((n.hop_count ?? 999) === 2) groups.h2.push(n);
      else if ((n.hop_count ?? 999) >= 3 && (n.hop_count ?? 999) < 999) groups.h3.push(n);
      else groups.hx.push(n);
    }

    // Calculate ring radii based on group sizes for better spacing
    const maxRadius = Math.min(size.w, size.h) * 0.4;
    const ringCount = 5;
    const baseRadius = maxRadius / ringCount;

    const pos = new Map<string, Point>();

    // Place local node in center
    if (groups.local.length && local) pos.set(local.id, center);

    // Improved ring placement with angular offset for better distribution
    const placeRing = (arr: NodeInfo[], radius: number, angleOffset: number = 0) => {
      const n = arr.length;
      if (n === 0) return;

      // Add some randomness to prevent perfect alignment
      const jitter = 0.1;
      const step = (2 * Math.PI) / n;

      for (let i = 0; i < n; i++) {
        const baseAngle = i * step + angleOffset;
        const angle = baseAngle + (Math.random() - 0.5) * jitter;
        const r = radius + (Math.random() - 0.5) * 20; // Small radius variation
        pos.set(arr[i].id, {
          x: center.x + r * Math.cos(angle),
          y: center.y + r * Math.sin(angle)
        });
      }
    };

    // Place nodes with angular offsets to prevent overlap between rings
    placeRing(groups.h0, baseRadius * 1.5, 0);
    placeRing(groups.h1, baseRadius * 2.5, Math.PI / 6);
    placeRing(groups.h2, baseRadius * 3.5, Math.PI / 3);
    placeRing(groups.h3.concat(groups.hx), baseRadius * 4.5, Math.PI / 2);

    return pos;
  }, [nodes, size, localNodeId]);

  // Basic analytics
  const stats = useMemo(() => {
    const total = nodes.length;
    const direct = nodes.filter(n => (n.hop_count ?? 999) === 0 && n.id !== localNodeId).length;
    const multi = nodes.filter(n => (n.hop_count ?? 999) >= 1 && (n.hop_count ?? 999) < 999).length;
    const unknown = nodes.filter(n => (n.hop_count ?? 999) >= 999).length;
    const avgHop = (() => {
      const hs = nodes
        .filter(n => typeof n.hop_count === 'number' && (n.hop_count as number) < 999 && n.id !== localNodeId)
        .map(n => n.hop_count as number);
      if (!hs.length) return 0;
      return +(hs.reduce((a, b) => a + b, 0) / hs.length).toFixed(2);
    })();
    return { total, direct, multi, unknown, avgHop };
  }, [nodes, localNodeId]);

  return (
    <div className="w-full h-full bg-gray-900 relative">
      <svg
        ref={svgRef}
        width="100%"
        height="100%"
        viewBox={`0 0 ${size.w} ${size.h}`}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredNode(null)}
      >
        {/* Links */}
        {filteredLinks.map((l, idx) => {
          const a = layout.get(l.from_id);
          const b = layout.get(l.to_id);
          if (!a || !b) return null;
          const cls = l.is_direct ? '#22d3ee' : '#64748b';
          const opacity = l.is_direct ? 0.7 : 0.3;
          const width = l.is_direct ? 2 : 1;
          return (
            <line
              key={idx}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={cls}
              strokeOpacity={opacity}
              strokeWidth={width}
              strokeDasharray={l.is_direct ? '0' : '4 2'}
            />
          );
        })}
        {/* Nodes */}
        {nodes.map((n) => {
          const p = layout.get(n.id);
          if (!p) return null;
          const isLocal = n.id === localNodeId;
          const hops = n.hop_count ?? 999;
          const r = isLocal ? 10 : hops === 0 ? 7 : hops === 1 ? 6 : 5;
          const fill = isLocal ? '#22c55e' : hops === 0 ? '#38bdf8' : '#94a3b8';
          const stroke = isLocal ? '#22c55e' : '#0ea5e9';
          const isHovered = hoveredNode === n.id;
          const showLabel = isLocal; // Only show label for local node to reduce clutter
          const actualRadius = isHovered ? r + 3 : r;
          return (
            <g key={n.id}>
              <circle
                cx={p.x}
                cy={p.y}
                r={actualRadius}
                fill={fill}
                fillOpacity={isHovered ? 1 : 0.9}
                stroke={stroke}
                strokeWidth={isLocal ? 3 : isHovered ? 2 : 1}
                style={{ cursor: 'pointer', transition: 'all 0.2s' }}
                onMouseEnter={() => setHoveredNode(n.id)}
                onMouseLeave={() => setHoveredNode(null)}
              />
              {showLabel && (
                <text
                  x={p.x}
                  y={p.y - r - 8}
                  fontSize={12}
                  fontWeight="bold"
                  fill="#22c55e"
                  textAnchor="middle"
                  style={{ pointerEvents: 'none' }}
                >
                  {n.short_name || 'LOCAL'}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <div className="absolute top-2 right-3 bg-gray-800/80 text-gray-200 text-xs px-2 py-1 rounded border border-gray-700">
        Nodes: {stats.total} (Direct {stats.direct}, Multi {stats.multi}, Unk {stats.unknown}) • Avg hop: {stats.avgHop}
      </div>
      {hoveredNode && (() => {
        const node = nodeMap.get(hoveredNode);
        if (!node) return null;
        return (
          <div
            className="absolute bg-gray-800 text-white text-xs px-2 py-1 rounded border border-gray-600 pointer-events-none z-10"
            style={{
              left: `${mousePos.x + 10}px`,
              top: `${mousePos.y - 30}px`,
              maxWidth: '200px'
            }}
          >
            <div className="font-semibold">{node.long_name || node.short_name || 'Unknown'}</div>
            <div className="text-gray-400">ID: {node.id.slice(0, 8)}</div>
            {node.hop_count !== undefined && node.hop_count < 999 && (
              <div className="text-gray-400">Hops: {node.hop_count}</div>
            )}
            {node.rssi && node.hop_count === 0 && <div className="text-gray-400">RSSI: {node.rssi} dBm</div>}
          </div>
        );
      })()}
    </div>
  );
};

export default NetworkViz;

