import { useState } from 'react';
import { Network, TreePine, Grid3x3, Table } from 'lucide-react';
import { NetworkViz } from './NetworkViz';
import { NetworkTree } from './NetworkTree';
import type { NodeInfo, NetworkLink } from '../types';

interface NetworkViewerProps {
  nodes: NodeInfo[];
  links: NetworkLink[];
  localNodeId?: string | null;
}

type ViewMode = 'radial' | 'tree' | 'grid' | 'table';

export const NetworkViewer = ({ nodes, links, localNodeId }: NetworkViewerProps) => {
  const [viewMode, setViewMode] = useState<ViewMode>('radial');

  const renderView = () => {
    switch (viewMode) {
      case 'radial':
        return <NetworkViz nodes={nodes} links={links} localNodeId={localNodeId} />;
      case 'tree':
        return <NetworkTree nodes={nodes} links={links} localNodeId={localNodeId} />;
      case 'grid':
        return <NetworkGrid nodes={nodes} links={links} localNodeId={localNodeId} />;
      case 'table':
        return <NetworkTable nodes={nodes} links={links} localNodeId={localNodeId} />;
      default:
        return <NetworkViz nodes={nodes} links={links} localNodeId={localNodeId} />;
    }
  };

  return (
    <div className="h-full flex flex-col bg-gray-900">
      <div className="flex items-center gap-2 p-2 border-b border-gray-700">
        <span className="text-xs text-gray-400 mr-2">View:</span>
        <button
          onClick={() => setViewMode('radial')}
          className={`px-3 py-1 text-xs rounded flex items-center gap-1 transition-colors ${
            viewMode === 'radial'
              ? 'bg-cyan-600 text-white'
              : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
          }`}
          title="Radial layout by hop distance"
        >
          <Network className="h-3 w-3" />
          Radial
        </button>
        <button
          onClick={() => setViewMode('tree')}
          className={`px-3 py-1 text-xs rounded flex items-center gap-1 transition-colors ${
            viewMode === 'tree'
              ? 'bg-cyan-600 text-white'
              : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
          }`}
          title="Hierarchical tree view"
        >
          <TreePine className="h-3 w-3" />
          Tree
        </button>
        <button
          onClick={() => setViewMode('grid')}
          className={`px-3 py-1 text-xs rounded flex items-center gap-1 transition-colors ${
            viewMode === 'grid'
              ? 'bg-cyan-600 text-white'
              : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
          }`}
          title="Grid layout by signal strength"
        >
          <Grid3x3 className="h-3 w-3" />
          Grid
        </button>
        <button
          onClick={() => setViewMode('table')}
          className={`px-3 py-1 text-xs rounded flex items-center gap-1 transition-colors ${
            viewMode === 'table'
              ? 'bg-cyan-600 text-white'
              : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
          }`}
          title="Table view with sortable columns"
        >
          <Table className="h-3 w-3" />
          Table
        </button>
      </div>
      <div className="flex-1 min-h-0">
        {renderView()}
      </div>
    </div>
  );
};

// Grid view component - arranges nodes by signal quality
const NetworkGrid = ({ nodes, localNodeId }: { nodes: NodeInfo[]; links: NetworkLink[]; localNodeId?: string | null }) => {
  // Sort nodes by signal strength and hop count
  const sortedNodes = [...nodes].sort((a, b) => {
    // Local node first
    if (a.id === localNodeId) return -1;
    if (b.id === localNodeId) return 1;

    // Then by hop count
    const hopA = a.hop_count ?? 999;
    const hopB = b.hop_count ?? 999;
    if (hopA !== hopB) return hopA - hopB;

    // Then by signal strength
    const rssiA = a.rssi ?? -999;
    const rssiB = b.rssi ?? -999;
    return rssiB - rssiA;
  });

  const getNodeColor = (node: NodeInfo) => {
    if (node.id === localNodeId) return 'bg-green-600';
    const hops = node.hop_count ?? 999;
    if (hops === 0) return 'bg-blue-600';
    if (hops === 1) return 'bg-cyan-600';
    if (hops === 2) return 'bg-purple-600';
    return 'bg-gray-600';
  };

  const getSignalBars = (rssi?: number) => {
    if (!rssi) return 0;
    if (rssi > -70) return 4;
    if (rssi > -80) return 3;
    if (rssi > -90) return 2;
    if (rssi > -100) return 1;
    return 0;
  };

  return (
    <div className="h-full overflow-auto bg-gray-900 p-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-2">
        {sortedNodes.map(node => (
          <div
            key={node.id}
            className={`${getNodeColor(node)} rounded-lg p-2 text-white text-xs hover:scale-105 transition-transform cursor-pointer`}
            title={`${node.long_name || node.short_name || node.id}\nHops: ${node.hop_count ?? 'Unknown'}\nRSSI: ${node.rssi ?? 'N/A'}`}
          >
            <div className="font-semibold truncate">
              {node.short_name || node.id.slice(0, 8)}
            </div>
            <div className="text-gray-200 text-[10px]">
              {node.hop_count !== undefined && node.hop_count < 999 ? `${node.hop_count}h` : '?h'}
            </div>
            {node.hop_count === 0 && (
              <div className="flex gap-0.5 mt-1">
                {[...Array(4)].map((_, i) => (
                  <div
                    key={i}
                    className={`h-2 w-1 ${
                      i < getSignalBars(node.rssi) ? 'bg-white' : 'bg-gray-500'
                    }`}
                  />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// Table view component - sortable data table
const NetworkTable = ({ nodes, localNodeId }: { nodes: NodeInfo[]; links: NetworkLink[]; localNodeId?: string | null }) => {
  const [sortKey, setSortKey] = useState<keyof NodeInfo>('hop_count');
  const [sortAsc, setSortAsc] = useState(true);

  const handleSort = (key: keyof NodeInfo) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  const sortedNodes = [...nodes].sort((a, b) => {
    const aVal = a[sortKey];
    const bVal = b[sortKey];

    // Handle nulls/undefined
    if (aVal === null || aVal === undefined) return 1;
    if (bVal === null || bVal === undefined) return -1;

    // Compare
    if (aVal < bVal) return sortAsc ? -1 : 1;
    if (aVal > bVal) return sortAsc ? 1 : -1;
    return 0;
  });

  return (
    <div className="h-full overflow-auto bg-gray-900">
      <table className="w-full text-xs text-gray-300">
        <thead className="bg-gray-800 sticky top-0">
          <tr>
            <th className="px-2 py-1 text-left cursor-pointer hover:bg-gray-700" onClick={() => handleSort('short_name')}>
              Name {sortKey === 'short_name' && (sortAsc ? '↑' : '↓')}
            </th>
            <th className="px-2 py-1 text-left cursor-pointer hover:bg-gray-700" onClick={() => handleSort('id')}>
              ID {sortKey === 'id' && (sortAsc ? '↑' : '↓')}
            </th>
            <th className="px-2 py-1 text-left cursor-pointer hover:bg-gray-700" onClick={() => handleSort('hop_count')}>
              Hops {sortKey === 'hop_count' && (sortAsc ? '↑' : '↓')}
            </th>
            <th className="px-2 py-1 text-left cursor-pointer hover:bg-gray-700" onClick={() => handleSort('rssi')}>
              RSSI {sortKey === 'rssi' && (sortAsc ? '↑' : '↓')}
            </th>
            <th className="px-2 py-1 text-left cursor-pointer hover:bg-gray-700" onClick={() => handleSort('snr')}>
              SNR {sortKey === 'snr' && (sortAsc ? '↑' : '↓')}
            </th>
            <th className="px-2 py-1 text-left cursor-pointer hover:bg-gray-700" onClick={() => handleSort('battery_level')}>
              Battery {sortKey === 'battery_level' && (sortAsc ? '↑' : '↓')}
            </th>
            <th className="px-2 py-1 text-left cursor-pointer hover:bg-gray-700" onClick={() => handleSort('role')}>
              Role {sortKey === 'role' && (sortAsc ? '↑' : '↓')}
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedNodes.map(node => (
            <tr
              key={node.id}
              className={`border-t border-gray-800 hover:bg-gray-800 ${
                node.id === localNodeId ? 'bg-green-900/20 font-semibold' : ''
              }`}
            >
              <td className="px-2 py-1">{node.short_name || node.long_name || '-'}</td>
              <td className="px-2 py-1 font-mono text-[10px]">{node.id.slice(0, 8)}</td>
              <td className="px-2 py-1">
                {node.hop_count !== undefined && node.hop_count < 999 ? node.hop_count : '-'}
              </td>
              <td className="px-2 py-1">
                {node.rssi && node.hop_count === 0 ? `${node.rssi} dBm` : '-'}
              </td>
              <td className="px-2 py-1">
                {node.snr && node.hop_count === 0 ? `${node.snr} dB` : '-'}
              </td>
              <td className="px-2 py-1">
                {node.battery_level ? `${node.battery_level}%` : '-'}
              </td>
              <td className="px-2 py-1">{node.role || 'CLIENT'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default NetworkViewer;