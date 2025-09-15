import type { FC } from 'react';
import { useState, useMemo } from 'react';
import { PlayCircle, StopCircle, RefreshCw, Activity, Users, MessageSquare } from 'lucide-react';
import { Session } from '../types';

interface SessionControlsProps {
  session: Session | null;
  isConnected: boolean;
  nodeCount: number;
  messageCount: number;
  onNewSession: () => void;
  onConnect: () => void;
  onDisconnect: () => void;
  testChannelIndex?: number | null;
  onSetTestChannel?: (index: number | null) => void;
  channels?: Array<{ index: number; name?: string; encrypted?: boolean }>;
}

const SessionControls: FC<SessionControlsProps> = ({
  session,
  isConnected,
  nodeCount,
  messageCount,
  onNewSession,
  onConnect,
  onDisconnect,
  testChannelIndex,
  onSetTestChannel,
  channels
}) => {
  const [tcInput, setTcInput] = useState<string>(testChannelIndex !== null && testChannelIndex !== undefined ? String(testChannelIndex) : '');
  const encStatus = useMemo(() => {
    if (typeof testChannelIndex !== 'number' || !channels) return null;
    const found = channels.find(c => c.index === testChannelIndex);
    if (!found) return null;
    return found.encrypted ? 'Encrypted' : 'Unencrypted';
  }, [channels, testChannelIndex]);
  const formatDuration = (startTime: string) => {
    const start = new Date(startTime);
    const now = new Date();
    const diff = Math.floor((now.getTime() - start.getTime()) / 1000);
    
    const hours = Math.floor(diff / 3600);
    const minutes = Math.floor((diff % 3600) / 60);
    const seconds = diff % 60;
    
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    } else {
      return `${seconds}s`;
    }
  };

  return (
    <div className="h-16 bg-gray-800 border-b border-gray-700 flex items-center justify-between px-6">
      <div className="flex items-center gap-6">
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Activity className="w-6 h-6 text-cyan-400" />
          Meshtastic Visualizer
        </h1>
        
        <div className="flex items-center gap-2">
          {isConnected ? (
            <button
              onClick={onDisconnect}
              className="flex items-center gap-2 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-md transition-colors text-sm"
            >
              <StopCircle className="w-4 h-4" />
              Disconnect
            </button>
          ) : (
            <button
              onClick={onConnect}
              className="flex items-center gap-2 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded-md transition-colors text-sm"
            >
              <PlayCircle className="w-4 h-4" />
              Connect
            </button>
          )}
          
          <button
            onClick={onNewSession}
            className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors text-sm"
          >
            <RefreshCw className="w-4 h-4" />
            New Session
          </button>
        </div>
      </div>
      
      <div className="flex items-center gap-6">
        {session && (
          <>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-gray-400">Session Time:</span>
              <span className="text-white font-medium">
                {formatDuration(session.started_at)}
              </span>
            </div>
            
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-cyan-400" />
                <span className="text-white font-medium">{nodeCount}</span>
                <span className="text-gray-400 text-sm">nodes</span>
              </div>
              
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-purple-400" />
                <span className="text-white font-medium">{messageCount}</span>
                <span className="text-gray-400 text-sm">messages</span>
              </div>
            </div>
          </>
        )}
        
        <div className="flex items-center gap-4">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
          <span className="text-sm text-gray-400">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
          {onSetTestChannel && (
            <div className="flex items-center gap-2 text-xs text-gray-300">
              <span>Private ch:</span>
              <input
                type="number"
                min={0}
                max={7}
                value={tcInput}
                onChange={(e) => setTcInput(e.target.value)}
                placeholder={testChannelIndex !== null && testChannelIndex !== undefined ? String(testChannelIndex) : ''}
                className="w-16 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none"
                title="Set private channel index (0–7)"
              />
              <button
                className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded"
                onClick={() => {
                  const num = Number(tcInput);
                  if (!Number.isFinite(num)) return;
                  if (num < 0 || num > 7) return;
                  onSetTestChannel(num);
                }}
              >
                Set
              </button>
              <button
                className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded"
                onClick={() => { setTcInput(''); onSetTestChannel(null); }}
              >
                Clear
              </button>
              {encStatus && (
                <span className={`ml-2 px-2 py-0.5 rounded ${encStatus === 'Encrypted' ? 'bg-green-700 text-white' : 'bg-yellow-700 text-white'}`}
                  title={encStatus === 'Encrypted' ? 'PSK present for channel' : 'No PSK detected for channel'}>
                  {encStatus}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SessionControls;
