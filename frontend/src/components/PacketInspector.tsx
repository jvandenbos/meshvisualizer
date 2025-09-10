import React, { useState, useEffect, useRef } from 'react';
import { Search, Filter, Download, Pause, Play, Info, ChevronDown, ChevronRight, Copy, Terminal } from 'lucide-react';

interface Packet {
  id: string;
  timestamp: Date;
  from: string;
  to: string;
  type: string;
  portnum: string;
  payload: any;
  rssi?: number;
  snr?: number;
  hopCount?: number;
  channel?: number;
  encrypted?: boolean;
  raw?: string;
}

interface PacketInspectorProps {
  onPacketReceived?: (packet: Packet) => void;
}

// Meshtastic Protocol Decoder
class MeshtasticDecoder {
  static portNumToString(portNum: number): string {
    const portMap: { [key: number]: string } = {
      0: 'UNKNOWN',
      1: 'TEXT_MESSAGE',
      2: 'REMOTE_HARDWARE',
      3: 'POSITION',
      4: 'NODEINFO',
      5: 'ROUTING',
      6: 'ADMIN',
      67: 'TELEMETRY',
      68: 'ZPS',
      69: 'SIMULATOR',
      70: 'TRACEROUTE',
      71: 'NEIGHBORINFO',
      72: 'ATAK_PLUGIN',
      256: 'PRIVATE_APP',
      257: 'ATAK_FORWARDER',
      513: 'IP_TUNNEL',
    };
    return portMap[portNum] || `CUSTOM_${portNum}`;
  }

  static decodePacket(packet: any): Packet {
    const decoded: Packet = {
      id: `pkt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(packet.timestamp || Date.now()),
      from: packet.from_id || packet.from || 'unknown',
      to: packet.to_id || packet.to || 'unknown',
      type: packet.packet_type || 'UNKNOWN',
      portnum: this.portNumToString(packet.portnum || 0),
      payload: packet.payload || {},
      rssi: packet.rssi,
      snr: packet.snr,
      hopCount: packet.hop_count,
      channel: packet.channel,
      encrypted: packet.encrypted || false,
      raw: JSON.stringify(packet, null, 2),
    };

    // Decode specific payload types
    if (decoded.portnum === 'TEXT_MESSAGE' && packet.payload?.text) {
      decoded.payload = {
        text: packet.payload.text,
        decoded: true,
      };
    } else if (decoded.portnum === 'POSITION' && packet.payload) {
      decoded.payload = {
        latitude: packet.payload.latitude,
        longitude: packet.payload.longitude,
        altitude: packet.payload.altitude,
        time: packet.payload.time,
        decoded: true,
      };
    } else if (decoded.portnum === 'TELEMETRY' && packet.payload) {
      decoded.payload = {
        battery: packet.payload.battery_level,
        voltage: packet.payload.voltage,
        channelUtilization: packet.payload.channel_utilization,
        airtime: packet.payload.air_util_tx,
        decoded: true,
      };
    } else if (decoded.portnum === 'NODEINFO' && packet.payload) {
      decoded.payload = {
        id: packet.payload.id,
        shortName: packet.payload.short_name,
        longName: packet.payload.long_name,
        hardware: packet.payload.hw_model,
        role: packet.payload.role,
        decoded: true,
      };
    }

    return decoded;
  }

  static getPacketColor(portnum: string): string {
    const colorMap: { [key: string]: string } = {
      'TEXT_MESSAGE': 'text-blue-400',
      'POSITION': 'text-green-400',
      'TELEMETRY': 'text-yellow-400',
      'NODEINFO': 'text-purple-400',
      'ROUTING': 'text-orange-400',
      'ADMIN': 'text-red-400',
    };
    return colorMap[portnum] || 'text-gray-400';
  }
}

export const PacketInspector: React.FC<PacketInspectorProps> = ({ onPacketReceived }) => {
  const [packets, setPackets] = useState<Packet[]>([]);
  const [filteredPackets, setFilteredPackets] = useState<Packet[]>([]);
  const [selectedPacket, setSelectedPacket] = useState<Packet | null>(null);
  const [isPaused, setIsPaused] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState<string>('ALL');
  const [expandedPackets, setExpandedPackets] = useState<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // WebSocket connection to receive packets
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws');
    
    ws.onmessage = (event) => {
      if (isPaused) return;
      
      try {
        const data = JSON.parse(event.data);
        
        // Handle different message types
        if (data.type === 'mesh_packet' || data.type === 'text_message' || 
            data.type === 'position_update' || data.type === 'telemetry' ||
            data.type === 'node_info') {
          const packet = MeshtasticDecoder.decodePacket(data.data);
          
          setPackets(prev => {
            const newPackets = [packet, ...prev].slice(0, 1000); // Keep last 1000 packets
            return newPackets;
          });
          
          if (onPacketReceived) {
            onPacketReceived(packet);
          }
        }
      } catch (err) {
        console.error('Error parsing packet:', err);
      }
    };

    return () => {
      ws.close();
    };
  }, [isPaused, onPacketReceived]);

  // Filter packets based on search and type
  useEffect(() => {
    let filtered = [...packets];
    
    if (filterType !== 'ALL') {
      filtered = filtered.filter(p => p.portnum === filterType);
    }
    
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(p => 
        p.from.toLowerCase().includes(term) ||
        p.to.toLowerCase().includes(term) ||
        p.portnum.toLowerCase().includes(term) ||
        JSON.stringify(p.payload).toLowerCase().includes(term)
      );
    }
    
    setFilteredPackets(filtered);
  }, [packets, searchTerm, filterType]);

  // Auto-scroll to top when new packets arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current && filteredPackets.length > 0) {
      scrollRef.current.scrollTop = 0;
    }
  }, [filteredPackets, autoScroll]);

  const togglePacketExpansion = (packetId: string) => {
    setExpandedPackets(prev => {
      const newSet = new Set(prev);
      if (newSet.has(packetId)) {
        newSet.delete(packetId);
      } else {
        newSet.add(packetId);
      }
      return newSet;
    });
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const exportPackets = () => {
    const dataStr = JSON.stringify(packets, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    const exportFileDefaultName = `packets_${Date.now()}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const getPacketTypes = (): string[] => {
    const types = new Set(packets.map(p => p.portnum));
    return Array.from(types).sort();
  };

  return (
    <div className="flex h-full bg-gray-900">
      {/* Packet List */}
      <div className="flex-1 flex flex-col border-r border-gray-700">
        {/* Header */}
        <div className="bg-gray-800 border-b border-gray-700 p-3">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Terminal className="h-5 w-5 text-cyan-400" />
              <h2 className="text-lg font-semibold text-white">Packet Inspector</h2>
              <span className="text-sm text-gray-400">({filteredPackets.length} packets)</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsPaused(!isPaused)}
                className="p-2 hover:bg-gray-700 rounded transition-colors"
                title={isPaused ? 'Resume' : 'Pause'}
              >
                {isPaused ? <Play className="h-4 w-4 text-green-400" /> : <Pause className="h-4 w-4 text-yellow-400" />}
              </button>
              <button
                onClick={exportPackets}
                className="p-2 hover:bg-gray-700 rounded transition-colors"
                title="Export Packets"
              >
                <Download className="h-4 w-4 text-gray-400" />
              </button>
            </div>
          </div>
          
          {/* Search and Filter */}
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search packets..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:border-cyan-500"
              />
            </div>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:border-cyan-500"
            >
              <option value="ALL">All Types</option>
              {getPacketTypes().map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Packet List */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {filteredPackets.map(packet => {
            const isExpanded = expandedPackets.has(packet.id);
            const colorClass = MeshtasticDecoder.getPacketColor(packet.portnum);
            
            return (
              <div
                key={packet.id}
                className={`border-b border-gray-800 hover:bg-gray-800 transition-colors ${
                  selectedPacket?.id === packet.id ? 'bg-gray-800' : ''
                }`}
              >
                <div
                  className="p-3 cursor-pointer"
                  onClick={() => setSelectedPacket(packet)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            togglePacketExpansion(packet.id);
                          }}
                          className="hover:bg-gray-700 rounded p-0.5"
                        >
                          {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                        </button>
                        <span className="text-xs text-gray-500 font-mono">
                          {packet.timestamp.toLocaleTimeString('en-US', { hour12: false, fractionalSecondDigits: 3 })}
                        </span>
                        <span className={`text-xs font-semibold ${colorClass}`}>
                          {packet.portnum}
                        </span>
                        {packet.encrypted && (
                          <span className="text-xs bg-red-900 text-red-300 px-1 rounded">ENCRYPTED</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-gray-400">From:</span>
                        <span className="font-mono text-cyan-400">{packet.from}</span>
                        <span className="text-gray-400">→</span>
                        <span className="text-gray-400">To:</span>
                        <span className="font-mono text-cyan-400">{packet.to}</span>
                      </div>
                      {packet.rssi && (
                        <div className="flex items-center gap-3 text-xs text-gray-500 mt-1">
                          <span>RSSI: {packet.rssi} dBm</span>
                          {packet.snr && <span>SNR: {packet.snr} dB</span>}
                          {packet.hopCount !== undefined && <span>Hops: {packet.hopCount}</span>}
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* Expanded Content */}
                  {isExpanded && (
                    <div className="mt-3 p-2 bg-gray-900 rounded text-xs">
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-gray-400">Payload:</span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            copyToClipboard(JSON.stringify(packet.payload, null, 2));
                          }}
                          className="hover:bg-gray-700 rounded p-1"
                          title="Copy Payload"
                        >
                          <Copy className="h-3 w-3 text-gray-400" />
                        </button>
                      </div>
                      <pre className="text-gray-300 overflow-x-auto">
                        {JSON.stringify(packet.payload, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Status Bar */}
        <div className="bg-gray-800 border-t border-gray-700 px-3 py-2 flex items-center justify-between text-xs text-gray-400">
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="rounded"
              />
              <span>Auto-scroll</span>
            </label>
            <span>{isPaused ? 'Paused' : 'Live'}</span>
          </div>
          <span>Buffer: {packets.length}/1000</span>
        </div>
      </div>

      {/* Packet Details Panel */}
      {selectedPacket && (
        <div className="w-96 flex flex-col bg-gray-850">
          <div className="bg-gray-800 border-b border-gray-700 p-3">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <Info className="h-4 w-4" />
                Packet Details
              </h3>
              <button
                onClick={() => setSelectedPacket(null)}
                className="text-gray-400 hover:text-white"
              >
                ×
              </button>
            </div>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4">
            <div className="space-y-4">
              {/* Basic Info */}
              <div>
                <h4 className="text-sm font-semibold text-gray-300 mb-2">Basic Information</h4>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Type:</span>
                    <span className={MeshtasticDecoder.getPacketColor(selectedPacket.portnum)}>
                      {selectedPacket.portnum}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">From:</span>
                    <span className="font-mono text-cyan-400">{selectedPacket.from}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">To:</span>
                    <span className="font-mono text-cyan-400">{selectedPacket.to}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Timestamp:</span>
                    <span className="text-gray-300">{selectedPacket.timestamp.toLocaleString()}</span>
                  </div>
                </div>
              </div>

              {/* Signal Info */}
              {selectedPacket.rssi && (
                <div>
                  <h4 className="text-sm font-semibold text-gray-300 mb-2">Signal Information</h4>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-500">RSSI:</span>
                      <span className="text-gray-300">{selectedPacket.rssi} dBm</span>
                    </div>
                    {selectedPacket.snr && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">SNR:</span>
                        <span className="text-gray-300">{selectedPacket.snr} dB</span>
                      </div>
                    )}
                    {selectedPacket.hopCount !== undefined && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">Hop Count:</span>
                        <span className="text-gray-300">{selectedPacket.hopCount}</span>
                      </div>
                    )}
                    {selectedPacket.channel !== undefined && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">Channel:</span>
                        <span className="text-gray-300">{selectedPacket.channel}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Decoded Payload */}
              <div>
                <h4 className="text-sm font-semibold text-gray-300 mb-2">Decoded Payload</h4>
                <pre className="text-xs text-gray-300 bg-gray-900 p-2 rounded overflow-x-auto">
                  {JSON.stringify(selectedPacket.payload, null, 2)}
                </pre>
              </div>

              {/* Raw Data */}
              <div>
                <h4 className="text-sm font-semibold text-gray-300 mb-2">Raw Packet Data</h4>
                <pre className="text-xs text-gray-400 bg-gray-900 p-2 rounded overflow-x-auto">
                  {selectedPacket.raw}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};