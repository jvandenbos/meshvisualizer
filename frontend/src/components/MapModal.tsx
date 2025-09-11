import type { FC } from 'react';
import { NodeInfo } from '../types';
import { MapView } from './MapView';

interface MapModalProps {
  nodes: NodeInfo[];
  onClose: () => void;
  localNodeId?: string | null;
}

export const MapModal: FC<MapModalProps> = ({ nodes, onClose, localNodeId }) => {
  const nodesMap = new Map<string, NodeInfo>();
  nodes.forEach(n => nodesMap.set(n.id, n));
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-full max-w-4xl h-[70vh] bg-gray-900 rounded-lg border border-gray-700 shadow-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
          <h3 className="text-lg font-semibold text-white">Map (Optional)</h3>
          <button className="text-gray-400 hover:text-white" onClick={onClose}>×</button>
        </div>
        <div className="h-[calc(70vh-52px)] relative">
          <MapView nodes={nodesMap} localNodeId={localNodeId} />
          {/* Mini Legend */}
          <div className="absolute bottom-4 left-4 z-[1000] bg-gray-800 rounded-lg p-3 text-xs text-gray-300 border border-gray-700">
            <div className="font-semibold mb-2">Legend</div>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-emerald-500 border border-white" />
                <span>Local Node</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-sky-500 border border-white relative">
                  <div className="absolute -top-2 -right-3 bg-gray-800 border border-gray-600 rounded px-1 text-[9px]">D</div>
                </div>
                <span>Direct</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-sky-500 border border-white relative">
                  <div className="absolute -top-2 -right-3 bg-gray-800 border border-gray-600 rounded px-1 text-[9px]">2+</div>
                </div>
                <span>N hops</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-5 h-3 bg-gray-600 rounded-sm" />
                <span>Cluster of nearby nodes</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-gray-500 border border-white" />
                <span>Popup shows coordinates and altitude (precision varies)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MapModal;
