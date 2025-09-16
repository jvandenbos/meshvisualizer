import { useState, useEffect, useCallback, useRef } from 'react';
import type { AliasMap } from './utils/nameResolver';
import ActiveNodes from './components/ActiveNodes';
import EventTicker, { Event } from './components/EventTicker';
import SessionControls from './components/SessionControls';
import { NodeDetailsModal } from './components/NodeDetailsModal';
// MessagesPanel moved into MessagesModal
import { MessagesModal } from './components/MessagesModal';
import { PacketDetailsModal } from './components/PacketDetailsModal';
import { MapModal } from './components/MapModal';
import { ChatPanel } from './components/ChatPanel';
import type { DecodedPacket } from './utils/meshtasticDecoder';
import { NodeInfo, TextMessage, Session, NetworkLink } from './types';
import { NetworkViewer } from './components/NetworkViewer';
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
  const [isMessagesOpen, setIsMessagesOpen] = useState(false);
  const rightPaneRef = useRef<HTMLDivElement | null>(null);
  // Removed resizable split; reserve for future network viz
  const [aliases, setAliases] = useState<AliasMap>({});
  const [chatTargetId] = useState<string | null>(null);
  const [testChannelIndex, setTestChannelIndex] = useState<number | null>(null);
  const [channelsInfo, setChannelsInfo] = useState<Array<{ index: number; name?: string; encrypted?: boolean }>>([]);
  const [autoRepliesEnabled, setAutoRepliesEnabled] = useState<boolean>(true);
  const discoveredIdsRef = useRef<Set<string>>(new Set());
  const recentEventRef = useRef<Map<string, number>>(new Map());
  const messageKeysRef = useRef<Set<string>>(new Set());
  const [networkLinks, setNetworkLinks] = useState<NetworkLink[]>([]);

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
      if (Array.isArray(data.links)) setNetworkLinks(data.links);
      if (data.messages) {
        setMessages(data.messages);
        try {
          const set = messageKeysRef.current;
          for (const m of data.messages as TextMessage[]) {
            const ts = Math.round(new Date(m.timestamp).getTime() / 1000);
            const key = `${m.from_id}|${m.to_id}|${(m.message||'').trim()}|${ts}`;
            set.add(key);
          }
        } catch {}
      }
      try {
        // Pre-populate discovered set to avoid duplicate discovery events
        const set = discoveredIdsRef.current;
        (data.nodes || []).forEach((n: any) => { if (n?.id) set.add(String(n.id)); });
      } catch {}
    };
    const onNodeInfo = (data: any) => {
      const nodeData = data.node || data;
      updateNode(nodeData);
      const id = String(nodeData.id);
      const seen = discoveredIdsRef.current;
      if (!seen.has(id)) {
        seen.add(id);
        addEvent('node_discovered', `Node discovered: ${nodeData.short_name || nodeData.id}`);
      }
    };
    const onTextMessage = (data: TextMessage) => {
      console.log('[WS] text_message', data);
      try {
        const ts = Math.round(new Date(data.timestamp).getTime() / 1000);
        const key = `${data.from_id}|${data.to_id}|${(data.message||'').trim()}|${ts}`;
        const set = messageKeysRef.current;
        if (set.has(key)) return;
        set.add(key);
        // keep set bounded
        if (set.size > 1000) {
          // naive prune: reset
          messageKeysRef.current = new Set(Array.from(set).slice(-800));
        }
      } catch {}
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
    const onNetworkLink = (data: any) => {
      try {
        const link: NetworkLink = {
          from_id: data.from_id,
          to_id: data.to_id,
          rssi: data.rssi,
          snr: data.snr,
          success_rate: typeof data.success_rate === 'number' ? data.success_rate : 1,
          last_seen: data.timestamp,
          is_direct: !!data.is_direct
        };
        setNetworkLinks((prev) => {
          const map = new Map<string, NetworkLink>();
          for (const l of prev) map.set(`${l.from_id}-${l.to_id}`, l);
          map.set(`${link.from_id}-${link.to_id}`, link);
          return Array.from(map.values());
        });
      } catch {}
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
    const onNodeUpdate = (data: any) => {
      const nodeData = data.node || data;
      updateNode(nodeData);
      // No discovery event here; this is an update
    };
    websocketService.on('node_update', onNodeUpdate);
    websocketService.on('text_message', onTextMessage);
    websocketService.on('position_update', onPosition);
    websocketService.on('telemetry', onTelemetry);
    websocketService.on('session_reset', onSessionReset);
    websocketService.on('network_link', onNetworkLink);

    return () => {
      websocketService.off('connected', onConnected);
      websocketService.off('disconnected', onDisconnected);
      websocketService.off('initial_state', onInitial);
      websocketService.off('node_info', onNodeInfo);
      websocketService.off('node_update', onNodeUpdate);
      websocketService.off('text_message', onTextMessage);
      websocketService.off('position_update', onPosition);
      websocketService.off('telemetry', onTelemetry);
      websocketService.off('session_reset', onSessionReset);
      websocketService.off('network_link', onNetworkLink);
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

  // Messages moved to modal; right pane uses Chat only

  const addEvent = (type: Event['type'], text: string) => {
    const event: Event = {
      id: `${Date.now()}-${Math.random()}`,
      type,
      text,
      timestamp: new Date()
    };
    // Dedupe: suppress same type+text within 5 seconds
    try {
      const key = `${type}|${text}`;
      const now = Date.now();
      const map = recentEventRef.current;
      // purge
      for (const [k, t] of Array.from(map.entries())) {
        if (now - t > 5000) map.delete(k);
      }
      if (map.has(key)) {
        return;
      }
      map.set(key, now);
    } catch {}
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
        onOpenMessages={() => setIsMessagesOpen(true)}
        onOpenMap={() => setIsMapOpen(true)}
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
        {/* Right: Network (top) + Chat (bottom) */}
        <div ref={rightPaneRef} className="flex-1 min-h-0 flex flex-col">
          <div className="basis-1/2 min-h-[220px] border-b border-gray-700 overflow-hidden">
            <NetworkViewer nodes={nodes} links={networkLinks} localNodeId={localNodeId} />
          </div>
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

      {isMessagesOpen && (
        <MessagesModal
          onClose={() => setIsMessagesOpen(false)}
          onPacketClick={(p) => setPacketModal(p)}
          nodes={nodes}
          aliases={aliases}
          testChannelIndex={testChannelIndex}
          autoRepliesEnabled={autoRepliesEnabled}
          localNodeId={localNodeId}
          onReplyTo={(nodeId) => {
            setChatTargetId(nodeId);
            setIsMessagesOpen(false);
          }}
        />
      )}
    </div>
  );
}

export default App
