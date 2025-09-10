import React, { useState, useEffect, useCallback } from 'react';
import NetworkGraph from './components/NetworkGraph';
import ActiveNodes from './components/ActiveNodes';
import EventTicker, { Event } from './components/EventTicker';
import SessionControls from './components/SessionControls';
import { MapView } from './components/MapView';
import { PacketInspector } from './components/PacketInspector';
import { NodeInfo, NetworkLink, TextMessage, Session } from './types';
import websocketService from './services/websocket';
import { Network, Map, Terminal } from 'lucide-react';

type ViewMode = 'graph' | 'map' | 'packets';

function App() {
  // State management
  const [isConnected, setIsConnected] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [nodes, setNodes] = useState<NodeInfo[]>([]);
  const [links, setLinks] = useState<NetworkLink[]>([]);
  const [messages, setMessages] = useState<TextMessage[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('graph');

  // Initialize WebSocket connection
  useEffect(() => {
    connectWebSocket();

    return () => {
      websocketService.disconnect();
    };
  }, []);

  const connectWebSocket = async () => {
    try {
      await websocketService.connect();
      
      // Set up event listeners
      websocketService.on('connected', () => {
        setIsConnected(true);
        addEvent('connection', 'Connected to server');
      });

      websocketService.on('disconnected', () => {
        setIsConnected(false);
        addEvent('connection', 'Disconnected from server');
      });

      websocketService.on('initial_state', (data: any) => {
        console.log('Received initial_state with', data.nodes?.length || 0, 'nodes');
        if (data.session) setSession(data.session);
        if (data.nodes) {
          console.log('Setting nodes:', data.nodes);
          setNodes(data.nodes);
        }
        if (data.messages) setMessages(data.messages);
        if (data.links) setLinks(data.links);
      });

      websocketService.on('node_info', (data: any) => {
        console.log('Received node_info:', data);
        const nodeData = data.node || data;
        updateNode(nodeData);
        addEvent('node_discovered', `Node discovered: ${nodeData.short_name || nodeData.id}`);
      });

      websocketService.on('text_message', (data: TextMessage) => {
        setMessages(prev => [...prev.slice(-99), data]);
        addEvent('message', `${data.from_name}: ${data.message.substring(0, 50)}`);
      });

      websocketService.on('position_update', (data: any) => {
        updateNodePosition(data.node_id, data.latitude, data.longitude, data.altitude);
        addEvent('position', `Position update: ${data.node_id}`);
      });

      websocketService.on('telemetry', (data: any) => {
        updateNodeTelemetry(data.node_id, data.device_metrics);
        addEvent('telemetry', `Telemetry: ${data.node_id}`);
      });

      websocketService.on('network_link', (data: NetworkLink) => {
        updateLink(data);
      });

      websocketService.on('session_reset', (data: any) => {
        setSession(data.session);
        setNodes([]);
        setLinks([]);
        setMessages([]);
        setEvents([]);
        addEvent('connection', 'Session reset');
      });

    } catch (error) {
      console.error('Failed to connect:', error);
      addEvent('connection', 'Failed to connect to server');
    }
  };

  const addEvent = (type: Event['type'], text: string) => {
    const event: Event = {
      id: `${Date.now()}-${Math.random()}`,
      type,
      text,
      timestamp: new Date()
    };
    setEvents(prev => [...prev.slice(-99), event]);
  };

  const updateNode = (nodeData: Partial<NodeInfo>) => {
    setNodes(prev => {
      const index = prev.findIndex(n => n.id === nodeData.id);
      if (index >= 0) {
        const updated = [...prev];
        updated[index] = { ...updated[index], ...nodeData };
        return updated;
      } else {
        return [...prev, nodeData as NodeInfo];
      }
    });
  };

  const updateNodePosition = (nodeId: string, lat?: number, lon?: number, alt?: number) => {
    setNodes(prev => prev.map(node => 
      node.id === nodeId 
        ? { ...node, latitude: lat, longitude: lon, altitude: alt }
        : node
    ));
  };

  const updateNodeTelemetry = (nodeId: string, metrics: any) => {
    setNodes(prev => prev.map(node => 
      node.id === nodeId 
        ? { 
            ...node, 
            battery_level: metrics.batteryLevel,
            voltage: metrics.voltage
          }
        : node
    ));
  };

  const updateLink = (link: NetworkLink) => {
    // Skip invalid links (broadcast or non-existent nodes)
    if (!link.from_id || !link.to_id || link.to_id === 'broadcast' || link.from_id === 'broadcast') {
      return;
    }
    
    setLinks(prev => {
      const index = prev.findIndex(l => 
        l.from_id === link.from_id && l.to_id === link.to_id
      );
      if (index >= 0) {
        const updated = [...prev];
        updated[index] = link;
        return updated;
      } else {
        return [...prev, link];
      }
    });
  };

  const handleNewSession = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/session/new', {
        method: 'POST'
      });
      const newSession = await response.json();
      setSession(newSession);
    } catch (error) {
      console.error('Failed to create new session:', error);
    }
  };

  const handleConnect = async () => {
    try {
      await fetch('http://localhost:8000/api/device/connect', {
        method: 'POST'
      });
    } catch (error) {
      console.error('Failed to connect device:', error);
    }
  };

  const handleDisconnect = async () => {
    try {
      await fetch('http://localhost:8000/api/device/disconnect', {
        method: 'POST'
      });
    } catch (error) {
      console.error('Failed to disconnect device:', error);
    }
  };

  const handleNodeSelect = useCallback((node: NodeInfo) => {
    setSelectedNodeId(node.id);
  }, []);

  const handleNodeClick = useCallback((node: NodeInfo) => {
    setSelectedNodeId(node.id);
    // Could open a detail panel or perform other actions
  }, []);

  const handleNodeHover = useCallback((node: NodeInfo | null) => {
    // Could show tooltip or highlight connections
  }, []);

  // Convert nodes array to Map for MapView
  const nodesMap = new Map<string, NodeInfo>();
  nodes.forEach(node => {
    nodesMap.set(node.id, node);
  });

  return (
    <div className="h-screen flex flex-col bg-gray-900">
      <SessionControls
        session={session}
        isConnected={isConnected}
        nodeCount={nodes.length}
        messageCount={messages.length}
        onNewSession={handleNewSession}
        onConnect={handleConnect}
        onDisconnect={handleDisconnect}
      />
      
      {/* View Mode Selector */}
      <div className="bg-gray-800 border-b border-gray-700 px-4 py-2">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode('graph')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded transition-colors ${
              viewMode === 'graph' 
                ? 'bg-cyan-600 text-white' 
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            <Network className="h-4 w-4" />
            <span className="text-sm font-medium">Network Graph</span>
          </button>
          <button
            onClick={() => setViewMode('map')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded transition-colors ${
              viewMode === 'map' 
                ? 'bg-cyan-600 text-white' 
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            <Map className="h-4 w-4" />
            <span className="text-sm font-medium">Coverage Map</span>
          </button>
          <button
            onClick={() => setViewMode('packets')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded transition-colors ${
              viewMode === 'packets' 
                ? 'bg-cyan-600 text-white' 
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            <Terminal className="h-4 w-4" />
            <span className="text-sm font-medium">Packet Inspector</span>
          </button>
        </div>
      </div>
      
      <div className="flex-1 flex overflow-hidden">
        {viewMode === 'graph' && (
          <>
            <div className="flex-1 p-4">
              <NetworkGraph
                nodes={nodes}
                links={links}
                onNodeClick={handleNodeClick}
                onNodeHover={handleNodeHover}
              />
            </div>
            <ActiveNodes
              nodes={nodes}
              selectedNodeId={selectedNodeId}
              onNodeSelect={handleNodeSelect}
              localNodeId="1109198442"
            />
          </>
        )}
        
        {viewMode === 'map' && (
          <>
            <div className="flex-1">
              <MapView
                nodes={nodesMap}
                localNodeId="1109198442"
                selectedNode={selectedNodeId}
                onNodeSelect={setSelectedNodeId}
              />
            </div>
            <ActiveNodes
              nodes={nodes}
              selectedNodeId={selectedNodeId}
              onNodeSelect={handleNodeSelect}
              localNodeId="1109198442"
            />
          </>
        )}
        
        {viewMode === 'packets' && (
          <div className="flex-1">
            <PacketInspector />
          </div>
        )}
      </div>
      
      {viewMode !== 'packets' && <EventTicker events={events} />}
    </div>
  );
}

export default App
