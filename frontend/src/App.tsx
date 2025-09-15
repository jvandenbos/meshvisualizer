import { useState, useEffect, useCallback, useRef } from 'react';
import type { AliasMap } from './utils/nameResolver';
import ActiveNodes from './components/ActiveNodes';
import EventTicker, { Event } from './components/EventTicker';
import SessionControls from './components/SessionControls';
import { NodeDetailsModal } from './components/NodeDetailsModal';
import { MessagesPanel } from './components/MessagesPanel';
import { PacketDetailsModal } from './components/PacketDetailsModal';
import { MapModal } from './components/MapModal';
import { ChatPanel } from './components/ChatPanel';
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
  const rightPaneRef = useRef<HTMLDivElement | null>(null);
  const [topHeight, setTopHeight] = useState<number>(300);
  const [isDragging, setIsDragging] = useState(false);
  const [aliases, setAliases] = useState<AliasMap>({});
  const [chatTargetId, setChatTargetId] = useState<string | null>(null);
  const [testChannelIndex, setTestChannelIndex] = useState<number | null>(null);
  const [channelsInfo, setChannelsInfo] = useState<Array<{ index: number; name?: string; encrypted?: boolean }>>([]);
  const [autoRepliesEnabled, setAutoRepliesEnabled] = useState<boolean>(true);

  // Connect once and register event handlers with cleanup to avoid duplicates
  useEffect(() => {
    websocketService.connect().catch((error) => {
      console.error('Failed to connect:', error);
      addEvent('connection', 'Failed to connect to server');
    });

    const onConnected = () => {
      setIsConnected(true);
      addEvent('connection', 'Connected to server');
    };
    const onDisconnected = () => {
      setIsConnected(false);
      addEvent('connection', 'Disconnected from server');
    };
    const onInitial = (data: any) => {
      console.log('Received initial_state with', data.nodes?.length || 0, 'nodes');
      if (data.session) setSession(data.session);
      if (data.nodes) setNodes(data.nodes);
      if (data.messages) setMessages(data.messages);
    };
    const onNodeInfo = (data: any) => {
      const nodeData = data.node || data;
      updateNode(nodeData);
      addEvent('node_discovered', `Node discovered: ${nodeData.short_name || nodeData.id}`);
    };
    const onTextMessage = (data: TextMessage) => {
      console.log('[WS] text_message', data);
      setMessages(prev => [...prev.slice(-99), data]);
      addEvent('message', `${data.from_name}: ${data.message.substring(0, 50)}`);
    };
    const onPosition = (data: any) => {
      updateNodePosition(data.node_id, data.latitude, data.longitude, data.altitude);
      addEvent('position', `Position update: ${data.node_id}`);
    };
    const onTelemetry = (data: any) => {
      updateNodeTelemetry(data.node_id, data.device_metrics);
      addEvent('telemetry', `Telemetry: ${data.node_id}`);
    };
    const onSessionReset = (data: any) => {
      setSession(data.session);
      setNodes([]);
      setMessages([]);
      setEvents([]);
      addEvent('connection', 'Session reset');
    };

    websocketService.on('connected', onConnected);
    websocketService.on('disconnected', onDisconnected);
    websocketService.on('initial_state', onInitial);
    websocketService.on('node_info', onNodeInfo);
    websocketService.on('text_message', onTextMessage);
    websocketService.on('position_update', onPosition);
    websocketService.on('telemetry', onTelemetry);
    websocketService.on('session_reset', onSessionReset);

    return () => {
      websocketService.off('connected', onConnected);
      websocketService.off('disconnected', onDisconnected);
      websocketService.off('initial_state', onInitial);
      websocketService.off('node_info', onNodeInfo);
      websocketService.off('text_message', onTextMessage);
      websocketService.off('position_update', onPosition);
      websocketService.off('telemetry', onTelemetry);
      websocketService.off('session_reset', onSessionReset);
      websocketService.disconnect();
    };
  }, []);

  // Fetch device status to get local node ID
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/device/status');
        const data = await res.json();
        if (data?.local_node_id) setLocalNodeId(String(data.local_node_id));
        if (data?.test_channel_index === 0 || data?.test_channel_index) setTestChannelIndex(Number(data.test_channel_index));
        if (typeof data?.auto_replies_enabled === 'boolean') setAutoRepliesEnabled(!!data.auto_replies_enabled);
      } catch (e) {
        // ignore
      }
    };
    fetchStatus();
    const fetchChannels = async () => {
      try {
        const r = await fetch('http://localhost:8000/api/device/channels');
        if (r.ok) {
          const info = await r.json();
          setChannelsInfo(info?.channels || []);
        }
      } catch {}
    };
    fetchChannels();
    // Load persisted private channel
    try {
      const stored = localStorage.getItem('testChannelIndex');
      if (stored !== null) {
        const idx = Number(stored);
        if (Number.isFinite(idx)) {
          setTestChannelIndex(idx);
          fetch('http://localhost:8000/api/channel/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ index: idx })
          }).catch(()=>{});
        }
      }
    } catch {}
    // Load optional aliases
    const fetchAliases = async () => {
      try {
        const r = await fetch('/aliases.json');
        if (r.ok) {
          const a = await r.json();
          setAliases(a || {});
        }
      } catch {
        // ignore if missing
      }
    };
    fetchAliases();
  }, []);

  // Refresh channels when connected or test channel changes
  useEffect(() => {
    const fetchChannels = async () => {
      try {
        const r = await fetch('http://localhost:8000/api/device/channels');
        if (r.ok) {
          const info = await r.json();
          setChannelsInfo(info?.channels || []);
        }
      } catch {}
    };
    if (isConnected) fetchChannels();
  }, [isConnected, testChannelIndex]);

  // Persist private channel selection
  useEffect(() => {
    try {
      if (typeof testChannelIndex === 'number') localStorage.setItem('testChannelIndex', String(testChannelIndex));
      else localStorage.removeItem('testChannelIndex');
    } catch {}
  }, [testChannelIndex]);

  // Initialize top height relative to pane size and update on resize
  useEffect(() => {
    const handleResize = () => {
      if (!rightPaneRef.current) return;
      const rect = rightPaneRef.current.getBoundingClientRect();
      const total = rect.height;
      const minTop = 160;
      const minBottom = 140;
      let desired = Math.max(minTop, Math.min(topHeight, total - minBottom));
      if (topHeight === 300) {
        // First-run heuristic ~ 65%
        desired = Math.max(minTop, Math.min(total * 0.65, total - minBottom));
      }
      setTopHeight(desired);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const onDividerMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    setIsDragging(true);
    e.preventDefault();
    const startY = e.clientY;
    const pane = rightPaneRef.current;
    if (!pane) return;
    const rect = pane.getBoundingClientRect();
    const startHeight = topHeight;
    const onMove = (ev: MouseEvent) => {
      const delta = ev.clientY - startY;
      const total = rect.height;
      const minTop = 160;
      const minBottom = 140;
      let newHeight = Math.max(minTop, Math.min(startHeight + delta, total - minBottom));
      setTopHeight(newHeight);
    };
    const onUp = () => {
      setIsDragging(false);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
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
    setNodes(prev => {
      const idx = prev.findIndex(n => n.id === nodeId);
      if (idx >= 0) {
        return prev.map(node => node.id === nodeId ? { ...node, latitude: lat, longitude: lon, altitude: alt } : node);
      }
      // Create minimal node if not present so it appears on map
      const minimal: NodeInfo = {
        id: nodeId,
        short_name: `Node-${String(nodeId).slice(0,8)}`,
        long_name: undefined,
        hardware_model: undefined,
        role: 'CLIENT',
        battery_level: undefined,
        voltage: undefined,
        rssi: undefined,
        snr: undefined,
        hop_count: 999,
        latitude: lat,
        longitude: lon,
        altitude: alt,
        last_heard: new Date().toISOString(),
        is_online: true,
        signal_quality: undefined
      };
      return [...prev, minimal];
    });
  };

  const updateNodeTelemetry = (nodeId: string, metrics: any) => {
    setNodes(prev => {
      const idx = prev.findIndex(n => n.id === nodeId);
      if (idx >= 0) {
        return prev.map(node => node.id === nodeId ? { ...node, battery_level: metrics.batteryLevel, voltage: metrics.voltage } : node);
      }
      const minimal: NodeInfo = {
        id: nodeId,
        short_name: `Node-${String(nodeId).slice(0,8)}`,
        hop_count: 999,
        is_online: true,
        last_heard: new Date().toISOString(),
        battery_level: metrics.batteryLevel,
        voltage: metrics.voltage
      } as NodeInfo;
      return [...prev, minimal];
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
        testChannelIndex={testChannelIndex ?? undefined}
        onSetTestChannel={async (idx) => {
          try {
            const res = await fetch('http://localhost:8000/api/channel/test', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ index: idx })
            });
            if (res.ok) {
              const data = await res.json();
              if (idx === null || idx === undefined) setTestChannelIndex(null);
              else setTestChannelIndex(Number(data.test_channel_index ?? idx));
            }
          } catch {}
        }}
        channels={channelsInfo}
        autoRepliesEnabled={autoRepliesEnabled}
        onToggleAutoReplies={async (enabled) => {
          try {
            const r = await fetch('http://localhost:8000/api/server/settings', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ auto_replies_enabled: enabled })
            });
            if (r.ok) {
              const d = await r.json();
              setAutoRepliesEnabled(!!d.auto_replies_enabled);
            }
          } catch {}
        }}
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
        {/* Right: Packets (top) + Chat (bottom) with resizable divider */}
        <div ref={rightPaneRef} className="flex-1 min-h-0 flex flex-col">
          <div className="min-h-0 border-b border-gray-700 overflow-hidden" style={{ height: topHeight }}>
            <MessagesPanel
              onPacketClick={(p) => setPacketModal(p)}
              onOpenMap={() => setIsMapOpen(true)}
              nodes={nodes}
              aliases={aliases}
              onReplyTo={(id) => setChatTargetId(id)}
            />
          </div>
          <div
            className={`h-2 bg-gray-800 border-y border-gray-700 ${isDragging ? 'cursor-row-resize bg-gray-700' : 'cursor-row-resize'} `}
            onMouseDown={onDividerMouseDown}
            title="Drag to resize"
          />
          <div className="flex-1 min-h-0 overflow-hidden">
            <ChatPanel nodes={nodes} messages={messages} localNodeId={localNodeId || undefined} targetNodeId={chatTargetId} testChannelIndex={testChannelIndex ?? undefined} />
          </div>
        </div>
      </div>

      <EventTicker events={events} />

      {selectedNode && (
        <NodeDetailsModal
          node={selectedNode}
          onClose={() => setSelectedNodeId(null)}
          onRequestTelemetry={(id) => websocketService.requestTelemetry(id)}
          onRequestPosition={(id) => websocketService.requestPosition(id)}
          testChannelIndex={testChannelIndex}
        />
      )}

      {packetModal && (
        <PacketDetailsModal packet={packetModal} onClose={() => setPacketModal(null)} />
      )}

      {isMapOpen && (
        <MapModal nodes={nodes} onClose={() => setIsMapOpen(false)} localNodeId={localNodeId} />
      )}
    </div>
  );
}

export default App
