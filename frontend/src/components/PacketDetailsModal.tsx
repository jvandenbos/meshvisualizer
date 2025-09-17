import type { FC } from 'react';
import MeshtasticDecoder, { DecodedPacket } from '../utils/meshtasticDecoder';
import {
  Info, X, Radio, Signal, Wifi, Hash, Clock,
  Navigation, Thermometer, MapPin,
  MessageSquare, User, Router, Zap
} from 'lucide-react';

interface PacketDetailsModalProps {
  packet: DecodedPacket;
  onClose: () => void;
}

export const PacketDetailsModal: FC<PacketDetailsModalProps> = ({ packet, onClose }) => {
  const hr = MeshtasticDecoder.toHumanReadable(packet);

  // Get packet type icon and color
  const getPacketTypeInfo = () => {
    switch (packet.portnum) {
      case 'TEXT_MESSAGE_APP':
        return { icon: MessageSquare, color: 'text-blue-400', bg: 'bg-blue-500/10' };
      case 'POSITION_APP':
        return { icon: MapPin, color: 'text-green-400', bg: 'bg-green-500/10' };
      case 'NODEINFO_APP':
        return { icon: User, color: 'text-purple-400', bg: 'bg-purple-500/10' };
      case 'TELEMETRY_APP':
        return { icon: Thermometer, color: 'text-orange-400', bg: 'bg-orange-500/10' };
      case 'ROUTING_APP':
        return { icon: Router, color: 'text-cyan-400', bg: 'bg-cyan-500/10' };
      default:
        return { icon: Radio, color: 'text-gray-400', bg: 'bg-gray-500/10' };
    }
  };

  const { icon: TypeIcon, color: typeColor, bg: typeBg } = getPacketTypeInfo();

  // Get signal quality color
  const getSignalColor = (rssi?: number) => {
    if (!rssi) return 'text-gray-500';
    if (rssi > -70) return 'text-green-400';
    if (rssi > -85) return 'text-yellow-400';
    if (rssi > -95) return 'text-orange-400';
    return 'text-red-400';
  };

  // Format timestamp
  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  };

  const formatDate = (date: Date) => {
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric'
    });
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="relative w-full max-w-3xl max-h-[90vh] bg-gray-900 rounded-xl border border-gray-700 shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700 bg-gray-800/50 rounded-t-xl">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${typeBg}`}>
              <TypeIcon className={`h-5 w-5 ${typeColor}`} />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">Packet Details</h3>
              <p className="text-xs text-gray-400">{packet.portnum}</p>
            </div>
          </div>
          <button
            className="p-1 rounded-lg hover:bg-gray-700 transition-colors"
            onClick={onClose}
            aria-label="Close"
          >
            <X className="h-5 w-5 text-gray-400 hover:text-white" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Routing Information */}
          <div className="bg-gray-800/30 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <Navigation className="h-4 w-4 text-cyan-400" />
              <h4 className="text-sm font-semibold text-gray-200">Routing</h4>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-gray-500 mb-1">From</p>
                <div className="flex items-center gap-2">
                  <User className="h-3 w-3 text-gray-400" />
                  <code className="text-sm text-cyan-400 font-mono">{packet.from}</code>
                </div>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">To</p>
                <div className="flex items-center gap-2">
                  <User className="h-3 w-3 text-gray-400" />
                  <code className="text-sm text-cyan-400 font-mono">{packet.to}</code>
                </div>
              </div>
              {packet.hopCount !== undefined && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">Hop Count</p>
                  <div className="flex items-center gap-2">
                    <Zap className="h-3 w-3 text-gray-400" />
                    <span className="text-sm text-gray-300">{packet.hopCount}</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Signal Information */}
          {(packet.rssi !== undefined || packet.snr !== undefined) && (
            <div className="bg-gray-800/30 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <Signal className="h-4 w-4 text-green-400" />
                <h4 className="text-sm font-semibold text-gray-200">Signal Quality</h4>
              </div>
              <div className="grid grid-cols-2 gap-4">
                {packet.rssi !== undefined && (
                  <div>
                    <p className="text-xs text-gray-500 mb-1">RSSI</p>
                    <div className="flex items-center gap-2">
                      <Wifi className={`h-3 w-3 ${getSignalColor(packet.rssi)}`} />
                      <span className={`text-sm font-semibold ${getSignalColor(packet.rssi)}`}>
                        {packet.rssi} dBm
                      </span>
                    </div>
                    <div className="mt-1 h-1 bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all ${
                          packet.rssi > -70 ? 'bg-green-400' :
                          packet.rssi > -85 ? 'bg-yellow-400' :
                          packet.rssi > -95 ? 'bg-orange-400' : 'bg-red-400'
                        }`}
                        style={{ width: `${Math.max(0, Math.min(100, (packet.rssi + 120) * 2))}%` }}
                      />
                    </div>
                  </div>
                )}
                {packet.snr !== undefined && (
                  <div>
                    <p className="text-xs text-gray-500 mb-1">SNR</p>
                    <div className="flex items-center gap-2">
                      <Signal className="h-3 w-3 text-gray-400" />
                      <span className="text-sm text-gray-300">{packet.snr} dB</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Metadata */}
          <div className="bg-gray-800/30 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <Info className="h-4 w-4 text-purple-400" />
              <h4 className="text-sm font-semibold text-gray-200">Metadata</h4>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-gray-500 mb-1">Time</p>
                <div className="flex items-center gap-2">
                  <Clock className="h-3 w-3 text-gray-400" />
                  <span className="text-sm text-gray-300">{formatTime(packet.timestamp)}</span>
                </div>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Date</p>
                <div className="flex items-center gap-2">
                  <Clock className="h-3 w-3 text-gray-400" />
                  <span className="text-sm text-gray-300">{formatDate(packet.timestamp)}</span>
                </div>
              </div>
              {packet.channel !== undefined && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">Channel</p>
                  <div className="flex items-center gap-2">
                    <Hash className="h-3 w-3 text-gray-400" />
                    <span className="text-sm text-gray-300">{packet.channel}</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Decoded Content */}
          {hr.fields.length > 0 && (
            <div className="bg-gray-800/30 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <TypeIcon className={`h-4 w-4 ${typeColor}`} />
                <h4 className="text-sm font-semibold text-gray-200">Decoded Content</h4>
              </div>
              <div className="space-y-2">
                {hr.fields.map((field, i) => (
                  <div key={i} className="flex items-start gap-3 py-1">
                    <span className="text-xs text-gray-500 min-w-[100px]">{field.label}:</span>
                    <span className="text-sm text-gray-300 font-mono break-all">{field.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Raw Data */}
          <details className="bg-gray-800/30 rounded-lg">
            <summary className="px-4 py-3 cursor-pointer hover:bg-gray-800/50 rounded-lg transition-colors">
              <span className="text-sm font-semibold text-gray-400">Raw Packet Data</span>
            </summary>
            <div className="p-4 pt-0">
              <pre className="text-xs text-gray-500 bg-black/30 p-3 rounded-lg overflow-x-auto font-mono">
                {packet.raw ? JSON.stringify(JSON.parse(packet.raw), null, 2) : 'No raw data available'}
              </pre>
            </div>
          </details>
        </div>
      </div>
    </div>
  );
};

export default PacketDetailsModal;