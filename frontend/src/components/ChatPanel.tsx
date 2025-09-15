import { useEffect, useMemo, useRef, useState } from 'react';
import { Send, UserCircle2 } from 'lucide-react';
import { TextMessage, NodeInfo } from '../types';
import { resolveName } from '../utils/nameResolver';
import websocketService from '../services/websocket';

interface ChatPanelProps {
  nodes: NodeInfo[];
  messages: TextMessage[];
  localNodeId?: string | null;
  targetNodeId?: string | null;
  testChannelIndex?: number | null;
}

type Pending = { id: string; text: string; dest: string; timestamp: number };

export const ChatPanel = ({ nodes, messages, localNodeId, targetNodeId, testChannelIndex }: ChatPanelProps) => {
  const [text, setText] = useState('');
  const [dest, setDest] = useState<string>('broadcast');
  const [isSending, setIsSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [pending, setPending] = useState<Pending[]>([]);
  const [usePrivateChannel, setUsePrivateChannel] = useState<boolean>(false);

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

  // Reconcile pending messages when we observe our own echo from backend
  useEffect(() => {
    if (!localNodeId) return;
    setPending((prev) => prev.filter((p) => {
      const delivered = messages.some((m) => {
        if (m.from_id !== localNodeId) return false;
        if ((m.message || '').trim() !== p.text.trim()) return false;
        const isBroadcast = m.to_id === 'broadcast' || m.to_id === '^all' || m.to_id === '4294967295';
        const destMatches = p.dest === 'broadcast' ? isBroadcast : (m.to_id === p.dest);
        return destMatches;
      });
      return !delivered;
    }));
  }, [messages, localNodeId]);

  // Safety: expire very old pending items to avoid infinite "Sending…"
  useEffect(() => {
    const iv = setInterval(() => {
      const now = Date.now();
      const ttlMs = 30000; // 30s TTL for pending
      setPending((prev) => prev.filter((p) => (now - p.timestamp) < ttlMs));
    }, 5000);
    return () => clearInterval(iv);
  }, []);

  // If a target node is provided (e.g., reply), switch destination
  useEffect(() => {
    if (!targetNodeId) return;
    setDest(targetNodeId);
  }, [targetNodeId]);

  const send = async () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    try {
      setIsSending(true);
      console.log('[Chat] send', { text: trimmed, dest });
      const channelIndex = usePrivateChannel && typeof testChannelIndex === 'number' ? testChannelIndex : undefined;
      websocketService.sendText(trimmed, dest === 'broadcast' ? undefined : dest, channelIndex);
      setPending((prev) => [{ id: `${Date.now()}-${Math.random()}`, text: trimmed, dest, timestamp: Date.now() }, ...prev].slice(0, 50));
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
            {typeof testChannelIndex === 'number' && (
              <label className="ml-2 inline-flex items-center gap-1 cursor-pointer select-none">
                <input type="checkbox" className="accent-purple-500" checked={usePrivateChannel} onChange={(e) => setUsePrivateChannel(e.target.checked)} />
                <span>Private ch {testChannelIndex}</span>
              </label>
            )}
          </div>
        </div>
      </div>

      {/* Messages Stream */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-1">
        {messages.length === 0 && (
          <div className="text-sm text-gray-500">No messages yet.</div>
        )}
        {/* Pending (sending) messages from me */}
        {pending.map((p) => (
          <div key={p.id} className="text-sm text-gray-400 italic">
            <span className="font-medium text-cyan-300">You</span>
            <span className="text-gray-500">: </span>
            <span className="whitespace-pre-wrap break-words">{p.text}</span>
            <span className="text-gray-500"> · Sending…</span>
          </div>
        ))}
        {/* Delivered messages */}
        {messages.map((m, i) => {
          const isMine = localNodeId && m.from_id === localNodeId;
          return (
            <div key={i} className="text-sm text-gray-200">
              <span className="font-medium text-cyan-300">{isMine ? 'You' : resolveName(m.from_id, nodes, undefined, m.from_name || m.from_id)}</span>
              <span className="text-gray-400">: </span>
              <span className="whitespace-pre-wrap break-words">{m.message}</span>
              {isMine && (
                <span className="text-gray-500 text-xs"> · ✓ Delivered {new Date(m.timestamp).toLocaleTimeString()}</span>
              )}
            </div>
          );
        })}
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
