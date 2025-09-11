import { useEffect, useMemo, useRef, useState } from 'react';
import { Send, UserCircle2 } from 'lucide-react';
import { TextMessage, NodeInfo } from '../types';
import websocketService from '../services/websocket';

interface ChatPanelProps {
  nodes: NodeInfo[];
  messages: TextMessage[];
}

export const ChatPanel = ({ nodes, messages }: ChatPanelProps) => {
  const [text, setText] = useState('');
  const [dest, setDest] = useState<string>('broadcast');
  const [isSending, setIsSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const nodeOptions = useMemo(() => {
    const opts = [{ id: 'broadcast', name: 'Broadcast' }];
    for (const n of nodes) {
      opts.push({ id: n.id, name: n.long_name || n.short_name || n.id });
    }
    return opts;
  }, [nodes]);

  useEffect(() => {
    // Auto-scroll to bottom when a new text message is added
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length]);

  const send = async () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    try {
      setIsSending(true);
      websocketService.sendText(trimmed, dest === 'broadcast' ? undefined : dest);
      setText('');
    } finally {
      setIsSending(false);
    }
  };

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 p-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <UserCircle2 className="h-5 w-5 text-purple-400" />
            <h3 className="text-white font-semibold">Messenger</h3>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <span>Destination:</span>
            <select
              value={dest}
              onChange={(e) => setDest(e.target.value)}
              className="px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none"
            >
              {nodeOptions.map(o => (
                <option key={o.id} value={o.id}>{o.name}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Messages Stream */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-2">
        {messages.length === 0 && (
          <div className="text-sm text-gray-500">No messages yet.</div>
        )}
        {messages.map((m, i) => (
          <div key={i} className="bg-gray-800 border border-gray-700 rounded p-2">
            <div className="flex items-center justify-between text-xs text-gray-400">
              <div className="flex items-center gap-2">
                <span className="font-mono text-cyan-400">{m.from_name || m.from_id}</span>
                <span>→</span>
                <span className="font-mono text-cyan-400">{m.to_name || m.to_id}</span>
              </div>
              <span>{new Date(m.timestamp).toLocaleTimeString()}</span>
            </div>
            <div className="mt-1 text-gray-200 whitespace-pre-wrap break-words">{m.message}</div>
            <div className="mt-1 text-[11px] text-gray-500 flex items-center gap-3">
              {m.rssi !== undefined && <span>RSSI: {m.rssi} dBm</span>}
              {m.snr !== undefined && <span>SNR: {m.snr} dB</span>}
              {m.hop_count !== undefined && <span>Hops: {m.hop_count}</span>}
            </div>
          </div>
        ))}
      </div>

      {/* Composer */}
      <div className="bg-gray-800 border-t border-gray-700 p-3">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKey}
            placeholder="Type a message..."
            className="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:border-cyan-500"
          />
          <button
            onClick={send}
            disabled={isSending || !text.trim()}
            className="px-3 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 rounded text-white text-sm flex items-center gap-1"
          >
            <Send className="h-4 w-4" /> Send
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatPanel;

