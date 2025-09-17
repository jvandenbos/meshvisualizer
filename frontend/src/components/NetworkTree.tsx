import { useState, useMemo, useEffect, ReactElement } from 'react';
import { ChevronRight, ChevronDown, Radio, Router, Smartphone, Cpu } from 'lucide-react';
import type { NodeInfo, NetworkLink } from '../types';

interface NetworkTreeProps {
  nodes: NodeInfo[];
  links: NetworkLink[];
  localNodeId?: string | null;
}

interface TreeNode {
  node: NodeInfo;
  children: TreeNode[];
  depth: number;
}

export const NetworkTree = ({ nodes, links, localNodeId }: NetworkTreeProps) => {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  // Build tree structure from local node outward
  const tree = useMemo(() => {
    if (!localNodeId) {
      console.log('[NetworkTree] No local node ID');
      return null;
    }

    const nodeMap = new Map<string, NodeInfo>();
    nodes.forEach(n => nodeMap.set(n.id, n));

    const localNode = nodeMap.get(localNodeId);
    if (!localNode) {
      console.log('[NetworkTree] Local node not found in nodes');
      return null;
    }

    console.log(`[NetworkTree] Building tree with ${nodes.length} nodes, ${links.length} links`);

    // Build tree structure
    const root: TreeNode = { node: localNode, children: [], depth: 0 };

    // Group nodes by hop count (excluding local node)
    const nodesByHop = new Map<number, NodeInfo[]>();
    nodes.forEach(node => {
      if (node.id === localNodeId) return; // Skip local node
      const hopCount = node.hop_count ?? 999;
      if (!nodesByHop.has(hopCount)) nodesByHop.set(hopCount, []);
      nodesByHop.get(hopCount)!.push(node);
    });

    console.log('[NetworkTree] Nodes by hop count:', {
      direct: nodesByHop.get(0)?.length || 0,
      oneHop: nodesByHop.get(1)?.length || 0,
      twoHop: nodesByHop.get(2)?.length || 0,
      threeHop: nodesByHop.get(3)?.length || 0
    });

    // Add direct nodes (hop_count = 0) as immediate children
    const directNodes = nodesByHop.get(0) || [];
    directNodes.forEach(node => {
      root.children.push({
        node,
        children: [],
        depth: 1
      });
    });

    // Add 1-hop nodes as second level
    const oneHopNodes = nodesByHop.get(1) || [];
    if (root.children.length > 0) {
      // Distribute 1-hop nodes among direct nodes
      oneHopNodes.forEach((node, idx) => {
        const parentIdx = idx % root.children.length;
        root.children[parentIdx].children.push({
          node,
          children: [],
          depth: 2
        });
      });
    } else {
      // No direct nodes, add 1-hop as direct children
      oneHopNodes.forEach(node => {
        root.children.push({
          node,
          children: [],
          depth: 1
        });
      });
    }

    // Add 2-hop nodes as third level
    const twoHopNodes = nodesByHop.get(2) || [];
    if (root.children.length > 0) {
      twoHopNodes.forEach((node, idx) => {
        const firstLevelIdx = idx % root.children.length;
        const firstLevel = root.children[firstLevelIdx];

        if (firstLevel.children.length > 0) {
          // Add to existing second-level nodes
          const secondLevelIdx = idx % firstLevel.children.length;
          firstLevel.children[secondLevelIdx].children.push({
            node,
            children: [],
            depth: 3
          });
        } else {
          // Add as second-level node
          firstLevel.children.push({
            node,
            children: [],
            depth: 2
          });
        }
      });
    } else {
      // No children, add as direct
      twoHopNodes.forEach(node => {
        root.children.push({
          node,
          children: [],
          depth: 1
        });
      });
    }

    // Add remaining nodes (3+ hops and unknown)
    const remainingHops = [3, 4, 5, 6, 7, 8, 9, 999];
    remainingHops.forEach(hop => {
      const hopNodes = nodesByHop.get(hop) || [];
      if (root.children.length > 0) {
        hopNodes.forEach((node, idx) => {
          const firstLevelIdx = idx % root.children.length;
          const firstLevel = root.children[firstLevelIdx];

          if (firstLevel.children.length > 0) {
            const secondLevelIdx = idx % firstLevel.children.length;
            const secondLevel = firstLevel.children[secondLevelIdx];

            if (secondLevel.children.length < 10) { // Limit children per node
              secondLevel.children.push({
                node,
                children: [],
                depth: 3
              });
            }
          } else {
            firstLevel.children.push({
              node,
              children: [],
              depth: 2
            });
          }
        });
      } else {
        hopNodes.forEach(node => {
          root.children.push({
            node,
            children: [],
            depth: 1
          });
        });
      }
    });

    console.log(`[NetworkTree] Tree built: root has ${root.children.length} children`);
    return root;
  }, [nodes, links, localNodeId]);

  // Auto-expand first level after tree is built
  useEffect(() => {
    if (tree && localNodeId) {
      const expandSet = new Set<string>([localNodeId]);
      // Also expand nodes with children
      tree.children.forEach(child => {
        if (child.children.length > 0) {
          expandSet.add(child.node.id);
        }
      });
      setExpanded(expandSet);
      console.log('[NetworkTree] Auto-expanded nodes:', expandSet.size);
    }
  }, [tree, localNodeId]);

  const toggleExpand = (nodeId: string) => {
    const newExpanded = new Set(expanded);
    if (newExpanded.has(nodeId)) {
      newExpanded.delete(nodeId);
    } else {
      newExpanded.add(nodeId);
    }
    setExpanded(newExpanded);
  };

  const renderNode = (treeNode: TreeNode): ReactElement => {
    const { node, children, depth } = treeNode;
    const isExpanded = expanded.has(node.id);
    const hasChildren = children.length > 0;
    const isSelected = selectedNode === node.id;
    const isLocal = node.id === localNodeId;

    // Icon based on node type
    const getIcon = () => {
      if (isLocal) return <Radio className="h-4 w-4 text-green-400" />;
      if (node.role === 'ROUTER' || node.role === 'ROUTER_CLIENT') return <Router className="h-4 w-4 text-purple-400" />;
      if (node.role === 'REPEATER') return <Cpu className="h-4 w-4 text-orange-400" />;
      return <Smartphone className="h-4 w-4 text-blue-400" />;
    };

    // Signal quality color
    const getSignalColor = () => {
      if (!node.rssi) return 'text-gray-500';
      if (node.rssi > -70) return 'text-green-400';
      if (node.rssi > -85) return 'text-yellow-400';
      if (node.rssi > -95) return 'text-orange-400';
      return 'text-red-400';
    };

    return (
      <div key={node.id} className="select-none">
        <div
          className={`flex items-center gap-2 py-1 px-2 rounded hover:bg-gray-800 cursor-pointer ${
            isSelected ? 'bg-gray-800' : ''
          } ${isLocal ? 'font-semibold' : ''}`}
          style={{ paddingLeft: `${depth * 20 + 8}px` }}
          onClick={() => {
            setSelectedNode(node.id);
            if (hasChildren) toggleExpand(node.id);
          }}
        >
          {hasChildren ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                toggleExpand(node.id);
              }}
              className="hover:bg-gray-700 rounded p-0.5"
            >
              {isExpanded ? (
                <ChevronDown className="h-3 w-3 text-gray-400" />
              ) : (
                <ChevronRight className="h-3 w-3 text-gray-400" />
              )}
            </button>
          ) : (
            <div className="w-4" />
          )}

          {getIcon()}

          <span className={`flex-1 text-sm ${isLocal ? 'text-green-400' : 'text-gray-200'}`}>
            {node.short_name || node.long_name || node.id.slice(0, 8)}
          </span>

          {node.hop_count !== undefined && node.hop_count < 999 && (
            <span className="text-xs text-gray-500">
              {node.hop_count === 0 ? 'Direct' : `${node.hop_count} hop${node.hop_count !== 1 ? 's' : ''}`}
            </span>
          )}

          {node.rssi && node.hop_count === 0 && (
            <span className={`text-xs ${getSignalColor()}`}>
              {node.rssi}dBm
            </span>
          )}

          {hasChildren && (
            <span className="text-xs text-gray-600">
              ({children.length})
            </span>
          )}
        </div>

        {isExpanded && hasChildren && (
          <div>
            {children.map(child => renderNode(child))}
          </div>
        )}
      </div>
    );
  };

  if (!tree) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500">
        <div className="text-center">
          <Radio className="h-8 w-8 mx-auto mb-2" />
          <p>No local node detected</p>
          <p className="text-xs mt-1">Nodes: {nodes.length}, Local ID: {localNodeId || 'none'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full bg-gray-900 text-white overflow-auto">
      <div className="p-4">
        <div className="mb-4 text-sm text-gray-400">
          <div className="flex items-center gap-4 mb-2">
            <span className="flex items-center gap-1">
              <Radio className="h-3 w-3 text-green-400" /> Local
            </span>
            <span className="flex items-center gap-1">
              <Router className="h-3 w-3 text-purple-400" /> Router
            </span>
            <span className="flex items-center gap-1">
              <Smartphone className="h-3 w-3 text-blue-400" /> Client
            </span>
            <span className="flex items-center gap-1">
              <Cpu className="h-3 w-3 text-orange-400" /> Repeater
            </span>
          </div>
          <div className="text-xs">
            Click nodes to expand/collapse • {nodes.length} total nodes • {tree.children.length} direct connections
          </div>
        </div>

        <div className="border border-gray-700 rounded-lg p-2">
          {renderNode(tree)}
        </div>

        {selectedNode && (() => {
          const node = nodes.find(n => n.id === selectedNode);
          if (!node) return null;

          return (
            <div className="mt-4 p-3 bg-gray-800 rounded-lg border border-gray-700">
              <div className="text-sm font-semibold mb-2">Node Details</div>
              <div className="text-xs space-y-1 text-gray-400">
                <div>Name: <span className="text-gray-200">{node.long_name || node.short_name || 'Unknown'}</span></div>
                <div>ID: <span className="text-gray-200">{node.id}</span></div>
                {node.hardware_model && <div>Hardware: <span className="text-gray-200">{node.hardware_model}</span></div>}
                {node.role && <div>Role: <span className="text-gray-200">{node.role}</span></div>}
                {node.battery_level && <div>Battery: <span className="text-gray-200">{node.battery_level}%</span></div>}
                {node.last_heard && <div>Last Heard: <span className="text-gray-200">{new Date(node.last_heard).toLocaleTimeString()}</span></div>}
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
};

export default NetworkTree;