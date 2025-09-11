import { useState, useEffect, useCallback } from 'react';
import ActiveNodes from './components/ActiveNodes';
import EventTicker, { Event } from './components/EventTicker';
import SessionControls from './components/SessionControls';
import { NodeDetailsModal } from './components/NodeDetailsModal';
import { MessagesPanel } from './components/MessagesPanel';
import { PacketDetailsModal } from './components/PacketDetailsModal';
import { MapModal } from './components/MapModal';
import type { DecodedPacket } from './utils/meshtasticDecoder';
import { NodeInfo, TextMessage, Session } from './types';
import websocketService from './services/websocket';

function App() {
  // State management
  const [isConnected, setIsConnected] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [nodes, setNodes] = useState<NodeInfo[]>([]);
  const [messages, setMessages] = useState<TextMessage[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [localNodeId, setLocalNodeId] = useState<string | null>(null);
  const [packetModal, setPacketModal] = useState<DecodedPacket | null>(null);
  const [isMapOpen, setIsMapOpen] = useState(false);

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
        // links not used in simplified UI
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

      // network_link events ignored in simplified UI

      websocketService.on('session_reset', (data: any) => {
        setSession(data.session);
        setNodes([]);
        setMessages([]);
        setEvents([]);
        addEvent('connection', 'Session reset');
      });

    } catch (error) {
      console.error('Failed to connect:', error);
      addEvent('connection', 'Failed to connect to server');
    }
  };

  // Fetch device status to get local node ID
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/device/status');
        const data = await res.json();
        if (data?.local_node_id) setLocalNodeId(String(data.local_node_id));
      } catch (e) {
        // ignore
      }
    };
    fetchStatus();
  }, []);

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

  

  const selectedNode = selectedNodeId ? nodes.find(n => n.id === selectedNodeId) || null : null;

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
      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* Left: Nodes */}
        <div className="w-96 border-r border-gray-700 flex flex-col min-h-0">
          <ActiveNodes
            nodes={nodes}
            selectedNodeId={selectedNodeId}
            onNodeSelect={handleNodeSelect}
            localNodeId={localNodeId || 'unknown'}
          />
        </div>
        {/* Right: Messages */}
        <div className="flex-1 min-h-0">
          <MessagesPanel onPacketClick={(p) => setPacketModal(p)} onOpenMap={() => setIsMapOpen(true)} />
        </div>
      </div>

      <EventTicker events={events} />

      {selectedNode && (
        <NodeDetailsModal
          node={selectedNode}
          onClose={() => setSelectedNodeId(null)}
          onRequestTelemetry={(id) => websocketService.requestTelemetry(id)}
          onRequestPosition={(id) => websocketService.requestPosition(id)}
        />
      )}

      {packetModal && (
        <PacketDetailsModal packet={packetModal} onClose={() => setPacketModal(null)} />
      )}

      {isMapOpen && (
        <MapModal nodes={nodes} onClose={() => setIsMapOpen(false)} />
      )}
    </div>
  );
}

export default App
