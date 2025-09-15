import type { FC } from 'react';
import { X } from 'lucide-react';
import { MessagesPanel } from './MessagesPanel';
import type { NodeInfo } from '../types';
import type { AliasMap } from '../utils/nameResolver';
import type { DecodedPacket } from '../utils/meshtasticDecoder';

interface MessagesModalProps {
  onClose: () => void;
  onPacketClick?: (packet: DecodedPacket) => void;
  nodes?: NodeInfo[];
  aliases?: AliasMap;
  testChannelIndex?: number | null;
  autoRepliesEnabled?: boolean;
}

export const MessagesModal: FC<MessagesModalProps> = ({ onClose, onPacketClick, nodes, aliases, testChannelIndex, autoRepliesEnabled }) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-[90vw] h-[80vh] bg-gray-900 rounded-lg border border-gray-700 shadow-xl flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
          <div className="text-white font-semibold">Messages</div>
          <button className="text-gray-400 hover:text-white" onClick={onClose} aria-label="Close"><X className="h-5 w-5" /></button>
        </div>
        <div className="flex-1 min-h-0">
          <MessagesPanel
            onPacketClick={onPacketClick}
            nodes={nodes}
            aliases={aliases}
            testChannelIndex={testChannelIndex}
            autoRepliesEnabled={autoRepliesEnabled}
          />
        </div>
      </div>
    </div>
  );
};

export default MessagesModal;

