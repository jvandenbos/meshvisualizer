import { useMemo, useRef, useEffect, useState } from 'react';
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

  const nodeMap = useMemo(() => {
    const map = new Map<string, NodeInfo>();
    for (const n of nodes) map.set(n.id, n);
    return map;
  }, [nodes]);

  const filteredLinks = useMemo(() => {
    return links.filter(l => nodeMap.has(l.from_id) && nodeMap.has(l.to_id));
  }, [links, nodeMap]);

  // Simple radial layout by hop_count
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
    const ringRadii = [0, Math.min(size.w, size.h) * 0.20, Math.min(size.w, size.h) * 0.34, Math.min(size.w, size.h) * 0.46, Math.min(size.w, size.h) * 0.54];
    const pos = new Map<string, Point>();
    // Local in center
    if (groups.local.length && local) pos.set(local.id, center);
    const placeRing = (arr: NodeInfo[], r: number) => {
      const n = arr.length;
      if (n === 0) return;
      const step = (2 * Math.PI) / n;
      for (let i = 0; i < n; i++) {
        const a = i * step - Math.PI / 2;
        pos.set(arr[i].id, { x: center.x + r * Math.cos(a), y: center.y + r * Math.sin(a) });
      }
    };
    placeRing(groups.h0, ringRadii[1]);
    placeRing(groups.h1, ringRadii[2]);
    placeRing(groups.h2, ringRadii[3]);
    placeRing(groups.h3.concat(groups.hx), ringRadii[4]);
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
    <div className="w-full h-full bg-gray-900">
      <svg ref={svgRef} width="100%" height="100%" viewBox={`0 0 ${size.w} ${size.h}`}>
        {/* Links */}
        {filteredLinks.map((l, idx) => {
          const a = layout.get(l.from_id);
          const b = layout.get(l.to_id);
          if (!a || !b) return null;
          const cls = l.is_direct ? '#22d3ee' : '#64748b';
          const opacity = l.is_direct ? 0.9 : 0.5;
          return (
            <line key={idx} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={cls} strokeOpacity={opacity} strokeWidth={l.is_direct ? 2.5 : 1.2} />
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
          return (
            <g key={n.id}>
              <circle cx={p.x} cy={p.y} r={r} fill={fill} stroke={stroke} strokeWidth={isLocal ? 2 : 1} />
              <text x={p.x + 8} y={p.y + 4} fontSize={11} fill="#e5e7eb">{n.long_name || n.short_name || n.id.slice(0, 8)}</text>
            </g>
          );
        })}
      </svg>
      <div className="absolute top-2 right-3 bg-gray-800/80 text-gray-200 text-xs px-2 py-1 rounded border border-gray-700">
        Nodes: {stats.total} (Direct {stats.direct}, Multi {stats.multi}, Unk {stats.unknown}) • Avg hop: {stats.avgHop}
      </div>
    </div>
  );
};

export default NetworkViz;

