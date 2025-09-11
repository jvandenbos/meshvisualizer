import type { FC } from 'react';
import { NodeInfo } from '../types';
import { MapView } from './MapView';

interface MapModalProps {
  nodes: NodeInfo[];
  onClose: () => void;
}

export const MapModal: FC<MapModalProps> = ({ nodes, onClose }) => {
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
        <div className="h-[calc(70vh-52px)]">
          <MapView nodes={nodesMap} />
        </div>
      </div>
    </div>
  );
};

export default MapModal;

