import React, { useState, useEffect } from 'react';
import { Key, AlertTriangle, Clock, Info } from 'lucide-react';

interface PKCInfo {
  node_id: string;
  node_name: string | null;
  current_key_hash: string;
  current_key: string;
  last_updated: string | null;
  age_hours: number | null;
  update_count: number;
  history_count: number;
  decryption_failures: number;
  last_failure: string | null;
}

interface PKCStatusProps {
  message: any; // The encrypted packet message
}

const PKCStatus: React.FC<PKCStatusProps> = ({ message }) => {
  const [showDetails, setShowDetails] = useState(false);
  const [pkcData, setPkcData] = useState<PKCInfo | null>(null);
  const [loading, setLoading] = useState(false);

  // Extract PKC info from message if available
  useEffect(() => {
    if (message?.pkc_info) {
      setPkcData(message.pkc_info);
    }
  }, [message]);

  // Fetch detailed PKC info for the node
  const fetchPKCDetails = async () => {
    if (!message?.from_id) return;

    setLoading(true);
    try {
      const response = await fetch(`http://localhost:8000/api/pkc/node/${message.from_id}`);
      if (response.ok) {
        const data = await response.json();
        // Transform to PKCInfo format
        const info: PKCInfo = {
          node_id: message.from_id,
          node_name: data.node_name || null,
          current_key_hash: data.current_key_hash || "unknown",
          current_key: data.current_key || "",
          last_updated: data.last_updated,
          age_hours: data.age_hours || null,
          update_count: data.update_count || 0,
          history_count: data.history?.length || 0,
          decryption_failures: data.decryption_failures || 0,
          last_failure: data.last_failure
        };
        setPkcData(info);
      }
    } catch (error) {
      console.error('Failed to fetch PKC details:', error);
    } finally {
      setLoading(false);
    }
  };

  // Parse the enhanced error message
  const parseErrorMessage = () => {
    if (!message?.message) return null;

    // Extract PKC diagnostics from the message
    const match = message.message.match(/\[Encrypted DM - PKC failed\]\s*(.*)/);
    if (match && match[1]) {
      const parts = match[1].split(' | ');
      const info: any = {};

      parts.forEach(part => {
        const [key, value] = part.split(':');
        if (key && value) {
          info[key.trim()] = value.trim();
        }
      });

      return info;
    }
    return null;
  };

  const parsedInfo = parseErrorMessage();

  const formatAge = (hours: number | null) => {
    if (hours === null) return 'unknown';
    if (hours < 1) return '<1 hour';
    if (hours < 24) return `${hours.toFixed(1)} hours`;
    const days = hours / 24;
    return `${days.toFixed(1)} days`;
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'unknown';
    try {
      const date = new Date(dateStr);
      return date.toLocaleString();
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="inline-flex items-center gap-2">
      {/* Main PKC indicator */}
      <button
        onClick={() => {
          setShowDetails(!showDetails);
          if (!pkcData && !loading) {
            fetchPKCDetails();
          }
        }}
        className="inline-flex items-center gap-1 px-2 py-1 bg-red-900/30 text-red-400 rounded text-xs hover:bg-red-900/50 transition-colors"
      >
        <Key className="w-3 h-3" />
        PKC Failed
        {parsedInfo?.fails && (
          <span className="ml-1 text-red-300">({parsedInfo.fails}x)</span>
        )}
      </button>

      {/* Inline diagnostics from message */}
      {parsedInfo && (
        <div className="inline-flex items-center gap-2 text-xs">
          {parsedInfo.key && parsedInfo.key !== 'none' && (
            <span className="text-gray-500">
              Key: <span className="font-mono text-gray-400">{parsedInfo.key}</span>
            </span>
          )}
          {parsedInfo.age && (
            <span className="text-gray-500">
              Age: <span className="text-yellow-400">{parsedInfo.age}</span>
            </span>
          )}
          {parsedInfo.updates && (
            <span className="text-gray-500">
              Updates: <span className="text-blue-400">{parsedInfo.updates}</span>
            </span>
          )}
        </div>
      )}

      {/* Detailed PKC info popup */}
      {showDetails && (
        <div className="absolute z-50 mt-8 p-4 bg-gray-800 border border-gray-700 rounded-lg shadow-lg min-w-[400px]">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Key className="w-4 h-4 text-red-400" />
              PKC Diagnostics for {message.from_name || message.from_id}
            </h3>
            <button
              onClick={() => setShowDetails(false)}
              className="text-gray-400 hover:text-white"
            >
              ×
            </button>
          </div>

          {loading ? (
            <div className="text-gray-400 text-sm">Loading PKC details...</div>
          ) : pkcData ? (
            <div className="space-y-2 text-xs">
              {/* Current Key Status */}
              <div className="flex items-start gap-2">
                <Info className="w-3 h-3 text-blue-400 mt-0.5" />
                <div className="flex-1">
                  <div className="text-gray-400">Current Public Key:</div>
                  {pkcData.current_key ? (
                    <>
                      <div className="font-mono text-gray-300 break-all">
                        {pkcData.current_key.substring(0, 32)}...
                      </div>
                      <div className="text-gray-500">
                        Hash: {pkcData.current_key_hash}
                      </div>
                    </>
                  ) : (
                    <div className="text-red-400">No public key on record</div>
                  )}
                </div>
              </div>

              {/* Key Age */}
              {pkcData.last_updated && (
                <div className="flex items-start gap-2">
                  <Clock className="w-3 h-3 text-yellow-400 mt-0.5" />
                  <div className="flex-1">
                    <div className="text-gray-400">Last Updated:</div>
                    <div className="text-gray-300">
                      {formatDate(pkcData.last_updated)}
                      <span className="ml-2 text-yellow-400">
                        ({formatAge(pkcData.age_hours)} ago)
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Failure Stats */}
              <div className="flex items-start gap-2">
                <AlertTriangle className="w-3 h-3 text-red-400 mt-0.5" />
                <div className="flex-1">
                  <div className="text-gray-400">Decryption Failures:</div>
                  <div className="text-red-300">
                    {pkcData.decryption_failures} failures
                    {pkcData.last_failure && (
                      <span className="ml-2 text-gray-500">
                        (last: {formatDate(pkcData.last_failure)})
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Key History */}
              {pkcData.update_count > 0 && (
                <div className="flex items-start gap-2">
                  <Key className="w-3 h-3 text-green-400 mt-0.5" />
                  <div className="flex-1">
                    <div className="text-gray-400">Key History:</div>
                    <div className="text-gray-300">
                      {pkcData.update_count} updates, {pkcData.history_count} historical keys
                    </div>
                  </div>
                </div>
              )}

              {/* Recommendations */}
              <div className="mt-3 pt-3 border-t border-gray-700">
                <div className="text-yellow-400 text-xs font-semibold mb-1">Recommendations:</div>
                {!pkcData.current_key ? (
                  <div className="text-gray-300 text-xs">
                    • Request NodeInfo from this node to obtain public key
                  </div>
                ) : pkcData.age_hours && pkcData.age_hours > 24 ? (
                  <div className="text-gray-300 text-xs">
                    • Key is stale ({formatAge(pkcData.age_hours)} old), consider refreshing
                  </div>
                ) : pkcData.decryption_failures > 5 ? (
                  <div className="text-gray-300 text-xs">
                    • High failure rate, node may have changed keys
                  </div>
                ) : (
                  <div className="text-gray-300 text-xs">
                    • Key appears valid, failures may be due to network issues
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="text-gray-400 text-sm">No PKC data available</div>
          )}
        </div>
      )}
    </div>
  );
};

export default PKCStatus;