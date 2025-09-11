import type { FC } from 'react';
import MeshtasticDecoder, { DecodedPacket } from '../utils/meshtasticDecoder';
import { Info } from 'lucide-react';

interface PacketDetailsModalProps {
  packet: DecodedPacket;
  onClose: () => void;
}

export const PacketDetailsModal: FC<PacketDetailsModalProps> = ({ packet, onClose }) => {
  const hr = MeshtasticDecoder.toHumanReadable(packet);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-gray-900 rounded-lg border border-gray-700 shadow-xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
          <div className="flex items-center gap-2">
            <Info className="h-5 w-5 text-cyan-400" />
            <h3 className="text-lg font-semibold text-white">Packet Details</h3>
          </div>
          <button className="text-gray-400 hover:text-white" onClick={onClose}>×</button>
        </div>
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="space-y-1">
              <div className="flex justify-between"><span className="text-gray-500">Type:</span><span className="text-gray-300">{packet.portnum}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">From:</span><span className="font-mono text-cyan-400">{packet.from}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">To:</span><span className="font-mono text-cyan-400">{packet.to}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Timestamp:</span><span className="text-gray-300">{packet.timestamp.toLocaleString()}</span></div>
            </div>
            <div className="space-y-1">
              {packet.rssi !== undefined && (<div className="flex justify-between"><span className="text-gray-500">RSSI:</span><span className="text-gray-300">{packet.rssi} dBm</span></div>)}
              {packet.snr !== undefined && (<div className="flex justify-between"><span className="text-gray-500">SNR:</span><span className="text-gray-300">{packet.snr} dB</span></div>)}
              {packet.hopCount !== undefined && (<div className="flex justify-between"><span className="text-gray-500">Hops:</span><span className="text-gray-300">{packet.hopCount}</span></div>)}
              {packet.channel !== undefined && (<div className="flex justify-between"><span className="text-gray-500">Channel:</span><span className="text-gray-300">{packet.channel}</span></div>)}
            </div>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-gray-300 mb-2">Human Readable</h4>
            <div className="grid grid-cols-2 gap-2 text-sm text-gray-300">
              {hr.fields.map((f, i) => (
                <div key={i} className="flex items-start justify-between gap-2">
                  <span className="text-gray-500">{f.label}:</span>
                  <span className="text-right whitespace-pre-wrap break-words">{f.value}</span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-gray-300 mb-2">Raw Packet</h4>
            <pre className="text-xs text-gray-400 bg-gray-900 p-2 rounded overflow-x-auto">{packet.raw}</pre>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PacketDetailsModal;
