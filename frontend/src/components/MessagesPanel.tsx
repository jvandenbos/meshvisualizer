import { useEffect, useMemo, useRef, useState } from 'react';
import { Search, Download, Pause, Play, Terminal, ChevronRight, ChevronDown, Copy, Reply } from 'lucide-react';
import websocketService from '../services/websocket';
import MeshtasticDecoder, { DecodedPacket } from '../utils/meshtasticDecoder';
import { NodeInfo } from '../types';
import { resolveName, AliasMap } from '../utils/nameResolver';

type TabKey = 'ALL' | 'TEXT_MESSAGE' | 'TELEMETRY' | 'POSITION' | 'NODEINFO' | 'ROUTING' | 'ADMIN' | 'UNKNOWN';

interface MessagesPanelProps {
  onPacketClick?: (packet: DecodedPacket) => void;
  onOpenMap?: () => void;
  nodes?: NodeInfo[];
  aliases?: AliasMap;
  onReplyTo?: (nodeId: string) => void;
  testChannelIndex?: number | null;
  autoRepliesEnabled?: boolean;
}

export const MessagesPanel: React.FC<MessagesPanelProps> = ({ onPacketClick, onOpenMap, nodes, aliases, onReplyTo, testChannelIndex, autoRepliesEnabled }) => {
  const [packets, setPackets] = useState<DecodedPacket[]>([]);
  const [filterTab, setFilterTab] = useState<TabKey>('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  const [isPaused, setIsPaused] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [channelFilter, setChannelFilter] = useState<number | 'ALL'>('ALL');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleAny = (data: any) => {
      if (isPaused) return;
      try {
        const pkt = MeshtasticDecoder.decodePacket(data);
        setPackets((prev) => [pkt, ...prev].slice(0, 1000));
      } catch (e) {
        // ignore
      }
    };

    const handleInitial = () => {
      // No historical packets provided; ignore here
    };

    websocketService.on('initial_state', handleInitial);
    websocketService.on('mesh_packet', handleAny);
    websocketService.on('text_message', handleAny);
    websocketService.on('position_update', handleAny);
    websocketService.on('telemetry', handleAny);
    websocketService.on('node_info', handleAny);

    return () => {
      websocketService.off('initial_state', handleInitial);
      websocketService.off('mesh_packet', handleAny);
      websocketService.off('text_message', handleAny);
      websocketService.off('position_update', handleAny);
      websocketService.off('telemetry', handleAny);
      websocketService.off('node_info', handleAny);
    };
  }, [isPaused]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [filterTab, searchTerm]);

  const filteredPackets = useMemo(() => {
    let list = packets;
    if (filterTab !== 'ALL') list = list.filter((p) => p.portnum === filterTab);
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      list = list.filter((p) =>
        p.from.toLowerCase().includes(term) ||
        p.to.toLowerCase().includes(term) ||
        p.portnum.toLowerCase().includes(term) ||
        JSON.stringify(p.payload).toLowerCase().includes(term)
      );
    }
    if (channelFilter !== 'ALL') {
      list = list.filter((p) => p.channel === channelFilter);
    }
    // Sort by timestamp desc for stable ordering
    return [...list].sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
  }, [packets, filterTab, searchTerm, channelFilter]);

  const availableChannels = useMemo(() => {
    const set = new Set<number>();
    for (const p of packets) {
      if (typeof p.channel === 'number') set.add(p.channel);
    }
    return Array.from(set).sort((a,b)=>a-b);
  }, [packets]);

  const exportPackets = () => {
    const dataStr = JSON.stringify(packets, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', `packets_${Date.now()}.json`);
    linkElement.click();
  };

  const toggleExpanded = (id: string) => {
    setExpanded((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  };

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'ALL', label: 'All' },
    { key: 'TEXT_MESSAGE', label: 'Messages' },
    { key: 'TELEMETRY', label: 'Telemetry' },
    { key: 'POSITION', label: 'Position' },
    { key: 'NODEINFO', label: 'Node Info' },
    { key: 'ROUTING', label: 'Routing' },
    { key: 'ADMIN', label: 'Admin' },
    { key: 'UNKNOWN', label: 'Unknown' },
  ];

  return (
    <div className="flex h-full bg-gray-900">
      <div className="flex-1 flex flex-col">
        <div className="bg-gray-800 border-b border-gray-700 p-3">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Terminal className="h-5 w-5 text-cyan-400" />
              <h2 className="text-lg font-semibold text-white">Messages</h2>
              <span className="text-sm text-gray-400">({filteredPackets.length})</span>
              {typeof testChannelIndex === 'number' && (
                <span className="ml-2 text-[11px] px-2 py-0.5 rounded bg-purple-700 text-white border border-purple-600" title="Private channel index">
                  Priv ch {testChannelIndex}
                </span>
              )}
              {typeof autoRepliesEnabled === 'boolean' && (
                <span
                  className={`ml-1 text-[11px] px-2 py-0.5 rounded border ${autoRepliesEnabled ? 'bg-green-700 text-white border-green-600' : 'bg-red-700 text-white border-red-600'}`}
                  title="Bot auto replies status"
                >
                  {autoRepliesEnabled ? 'Auto ON' : 'Auto OFF'}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {onOpenMap && (
                <button onClick={onOpenMap} className="px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded text-gray-200" title="Open Map">
                  Map
                </button>
              )}
              <button
                onClick={() => setIsPaused((p) => !p)}
                className="p-2 hover:bg-gray-700 rounded transition-colors"
                title={isPaused ? 'Resume' : 'Pause'}
              >
                {isPaused ? <Play className="h-4 w-4 text-green-400" /> : <Pause className="h-4 w-4 text-yellow-400" />}
              </button>
              <button onClick={exportPackets} className="p-2 hover:bg-gray-700 rounded" title="Export">
                <Download className="h-4 w-4 text-gray-400" />
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2 mb-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              <input
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search messages..."
                className="w-full pl-9 pr-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div className="flex items-center gap-1">
              {tabs.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setFilterTab(t.key)}
                  className={`px-2.5 py-1.5 text-xs rounded border ${filterTab === t.key ? 'bg-cyan-600 border-cyan-500 text-white' : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'}`}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 ml-2">
              <span className="text-sm text-gray-400">Ch:</span>
              <select
                value={channelFilter === 'ALL' ? 'ALL' : String(channelFilter)}
                onChange={(e) => setChannelFilter(e.target.value === 'ALL' ? 'ALL' : Number(e.target.value))}
                className="px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none"
              >
                <option value="ALL">All</option>
                {availableChannels.map(ch => (
                  <option key={ch} value={ch}>{ch}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {filteredPackets.map((p) => {
            const isExpanded = expanded.has(p.id);
            const colorClass = MeshtasticDecoder.getPacketColor(p.portnum);
            const hr = MeshtasticDecoder.toHumanReadable(p);
            return (
              <div key={p.id} className={`border-b border-gray-800 hover:bg-gray-800 transition-colors`}>
                <div className="p-3 cursor-pointer" onClick={() => onPacketClick && onPacketClick(p)}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <button onClick={() => toggleExpanded(p.id)} className="hover:bg-gray-700 rounded p-0.5">
                          {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                        </button>
                        <span className="text-xs text-gray-500 font-mono">
                          {p.timestamp.toLocaleTimeString('en-US', { hour12: false, fractionalSecondDigits: 3 })}
                        </span>
                        <span className={`text-xs font-semibold ${colorClass}`}>{p.portnum}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-gray-400">From:</span>
                        <span className="text-cyan-400">{resolveName(p.from, nodes, aliases, p.from)}</span>
                        <span className="text-gray-400">→</span>
                        <span className="text-gray-400">To:</span>
                        <span className="text-cyan-400">{resolveName(p.to, nodes, aliases, p.to)}</span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-gray-500 mt-1">
                        {p.rssi !== undefined && <span>RSSI: {p.rssi} dBm</span>}
                        {p.snr !== undefined && <span>SNR: {p.snr} dB</span>}
                        {p.hopCount !== undefined && <span>Hops: {p.hopCount}</span>}
                        {typeof p.channel === 'number' && <span>Ch: {p.channel}</span>}
                      </div>
                    </div>
                    <div className="ml-2 flex items-center gap-2">
                      {p.portnum === 'TEXT_MESSAGE' && onReplyTo && (
                        <button
                          onClick={(e) => { e.stopPropagation(); onReplyTo(p.from); }}
                          className="px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded text-gray-200 flex items-center gap-1"
                          title="Reply to sender"
                        >
                          <Reply className="h-3 w-3" /> Reply
                        </button>
                      )}
                      <button
                        onClick={(e) => { e.stopPropagation(); onPacketClick && onPacketClick(p); }}
                        className="px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded text-gray-200"
                      >
                        Inspect
                      </button>
                    </div>
                  </div>
                  {isExpanded && (
                    <div className="mt-3 p-2 bg-gray-900 rounded text-xs">
                      <div className="mb-1 text-gray-400">Details</div>
                      <div className="grid grid-cols-2 gap-2 text-gray-300">
                        {hr.fields.map((f, idx) => (
                          <div key={idx} className="flex items-center justify-between">
                            <span className="text-gray-500">{f.label}:</span>
                            <span className="ml-2 text-right whitespace-pre-wrap break-words">{f.value}</span>
                          </div>
                        ))}
                      </div>
                      <div className="mt-2 flex items-center justify-between">
                        <span className="text-gray-500">Raw Payload</span>
                        <button onClick={() => navigator.clipboard.writeText(p.raw || '')} className="hover:bg-gray-700 rounded p-1" title="Copy">
                          <Copy className="h-3 w-3 text-gray-400" />
                        </button>
                      </div>
                      <pre className="text-gray-400 overflow-x-auto">{p.raw}</pre>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          {filteredPackets.length === 0 && (
            <div className="p-8 text-center text-gray-500">No messages yet</div>
          )}
        </div>

        <div className="bg-gray-800 border-t border-gray-700 px-3 py-2 flex items-center justify-between text-xs text-gray-400">
          <div className="flex items-center gap-3">
            <span>{isPaused ? 'Paused' : 'Live'}</span>
          </div>
          <span>Buffer: {packets.length}/1000</span>
        </div>
      </div>
    </div>
  );
};

export default MessagesPanel;
