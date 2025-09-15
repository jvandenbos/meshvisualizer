import type { FC } from 'react';
import { useState } from 'react';
import { NodeInfo } from '../types';
import { Battery, Radio, MapPin, Cpu, User, CalendarClock, Signal, Gauge, Info, Send } from 'lucide-react';
import SignalStrengthGauge from './SignalStrengthGauge';
import websocketService from '../services/websocket';

interface NodeDetailsModalProps {
  node: NodeInfo;
  onClose: () => void;
  onRequestTelemetry?: (nodeId: string) => void;
  onRequestPosition?: (nodeId: string) => void;
  testChannelIndex?: number | null;
}

export const NodeDetailsModal: FC<NodeDetailsModalProps> = ({ node, onClose, onRequestTelemetry, onRequestPosition, testChannelIndex }) => {
  const [messageText, setMessageText] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [sendHint, setSendHint] = useState<string | null>(null);
  const [usePrivateChannel, setUsePrivateChannel] = useState<boolean>(false);
  const formatLastHeard = (timestamp: string) => {
    const date = new Date(timestamp);
    return isNaN(date.getTime()) ? '—' : date.toLocaleString();
  };

  const hopLabel = () => {
    if (node.hop_count === 0) return 'LOCAL';
    if (node.hop_count === 1) return 'DIRECT';
    if (node.hop_count === undefined || node.hop_count === null || node.hop_count >= 999) return 'UNKNOWN';
    return `${node.hop_count} HOPS`;
  };

  const handleSend = async () => {
    const text = messageText.trim();
    if (!text) return;
    try {
      setIsSending(true);
      const channelIndex = usePrivateChannel && typeof testChannelIndex === 'number' ? testChannelIndex : undefined;
      websocketService.sendText(text, node.id, channelIndex);
      setMessageText('');
      setSendHint('Sent');
      setTimeout(() => setSendHint(null), 1500);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-full max-w-xl bg-gray-900 rounded-lg border border-gray-700 shadow-xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
          <div className="flex items-center gap-2">
            <Info className="h-5 w-5 text-cyan-400" />
            <h3 className="text-lg font-semibold text-white">Node Details</h3>
          </div>
          <button className="text-gray-400 hover:text-white" onClick={onClose}>×</button>
        </div>

        <div className="p-4 space-y-4">
          <div className="flex items-start gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h4 className="text-xl font-semibold text-white">{node.long_name || node.short_name}</h4>
                <span className="text-xs px-2 py-1 rounded border border-gray-600 text-gray-300">{hopLabel()}</span>
              </div>
              {node.short_name && node.long_name && (
                <div className="text-sm text-gray-400">{node.short_name}</div>
              )}
              <div className="mt-2 text-sm text-gray-400 flex items-center gap-3">
                {node.role && (<span className="flex items-center gap-1"><User className="h-3 w-3" />{node.role}</span>)}
                {node.hardware_model && (<span className="flex items-center gap-1"><Cpu className="h-3 w-3" />{node.hardware_model}</span>)}
              </div>
            </div>
            <SignalStrengthGauge rssi={node.rssi} quality={node.signal_quality} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-gray-800 rounded p-3 space-y-2">
              <div className="text-xs uppercase tracking-wide text-gray-400">Device</div>
              <div className="text-sm text-gray-300 flex items-center gap-2"><Battery className="h-4 w-4" /> Battery: {node.battery_level ?? '—'}%</div>
              <div className="text-sm text-gray-300">Voltage: {node.voltage !== undefined && node.voltage !== null ? `${node.voltage.toFixed(2)} V` : '—'}</div>
              <div className="text-sm text-gray-300 flex items-center gap-2"><Gauge className="h-4 w-4" /> SNR: {node.snr !== undefined && node.snr !== null ? `${node.snr.toFixed(1)} dB` : '—'}</div>
            </div>
            <div className="bg-gray-800 rounded p-3 space-y-2">
              <div className="text-xs uppercase tracking-wide text-gray-400">Radio</div>
              <div className="text-sm text-gray-300 flex items-center gap-2"><Signal className="h-4 w-4" /> RSSI: {node.rssi !== undefined && node.rssi !== null ? `${node.rssi} dBm` : '—'}</div>
              <div className="text-sm text-gray-300 flex items-center gap-2"><Radio className="h-4 w-4" /> Hops: {hopLabel()}</div>
              <div className="text-sm text-gray-300 flex items-center gap-2"><CalendarClock className="h-4 w-4" /> Last Heard: {formatLastHeard(node.last_heard)}</div>
            </div>
          </div>

          <div className="bg-gray-800 rounded p-3">
            <div className="text-xs uppercase tracking-wide text-gray-400 mb-2">Location</div>
            <div className="text-sm text-gray-300 flex items-center gap-2"><MapPin className="h-4 w-4" />
              {node.latitude && node.longitude ? (
                <span>{node.latitude.toFixed(5)}, {node.longitude.toFixed(5)} {node.altitude !== undefined && `• ${node.altitude} m`}</span>
              ) : (
                <span>Unknown</span>
              )}
            </div>
          </div>

          {(onRequestTelemetry || onRequestPosition) && (
            <div className="flex items-center justify-between gap-3">
              <div className="flex-1 flex items-center gap-2">
                <input
                  type="text"
                  value={messageText}
                  onChange={(e) => setMessageText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                  placeholder={`Message to ${node.long_name || node.short_name || node.id}`}
                  className="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:border-cyan-500"
                />
                {typeof testChannelIndex === 'number' && (
                  <label className="ml-1 inline-flex items-center gap-1 cursor-pointer select-none text-xs text-gray-300">
                    <input type="checkbox" className="accent-purple-500" checked={usePrivateChannel} onChange={(e) => setUsePrivateChannel(e.target.checked)} />
                    <span>Private ch {testChannelIndex}</span>
                  </label>
                )}
                <button
                  onClick={handleSend}
                  disabled={isSending || !messageText.trim()}
                  className="px-3 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 rounded text-white text-sm flex items-center gap-1"
                  title="Send message"
                >
                  <Send className="h-4 w-4" /> Send
                </button>
                {sendHint && <span className="text-xs text-gray-400">{sendHint}</span>}
              </div>
              <div className="flex items-center justify-end gap-2">
              {onRequestTelemetry && (
                <button
                  onClick={() => onRequestTelemetry(node.id)}
                  className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 rounded text-white text-sm"
                >
                  Request Telemetry
                </button>
              )}
              {onRequestPosition && (
                <button
                  onClick={() => onRequestPosition(node.id)}
                  className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-white text-sm"
                >
                  Request Position
                </button>
              )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default NodeDetailsModal;
