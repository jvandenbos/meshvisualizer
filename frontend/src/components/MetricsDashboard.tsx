import { useState, useEffect } from 'react';
import {
  Activity, AlertTriangle, Battery, Radio, Users, Wifi, TrendingUp,
  AlertCircle, CheckCircle, XCircle, Clock, MessageSquare, Network
} from 'lucide-react';

interface MetricsData {
  summary: {
    total_nodes: number;
    active_nodes: number;
    inactive_nodes: number;
    network_health_score: number;
  };
  node_categories: {
    by_role: Record<string, number>;
    by_hardware: Record<string, number>;
    by_hop_distance: Record<string, number>;
    by_battery_status: {
      critical: string[];
      low: string[];
      medium: string[];
      good: string[];
      external: string[];
    };
    by_signal_quality: {
      excellent: string[];
      good: string[];
      fair: string[];
      poor: string[];
      unknown: string[];
    };
  };
  topology: {
    total_edges: number;
    average_degree: number;
    max_degree: number;
    network_diameter: number;
    clustering_coefficient: number;
    connected_components: number;
    critical_nodes: string[];
    node_degrees: Record<string, number>;
  };
  communication: {
    total_messages: number;
    messages_last_hour: number;
    messages_last_24h: number;
    messages_per_minute: number;
    most_active_nodes: Record<string, number>;
    message_types: Record<string, number>;
    average_message_length: number;
  };
  performance: {
    average_rssi: number | null;
    min_rssi: number | null;
    max_rssi: number | null;
    average_snr: number | null;
    average_hop_count: number | null;
    max_hop_count: number | null;
    signal_quality_distribution: Record<string, number>;
    hop_distribution: Record<string, number>;
  };
  reliability: {
    estimated_packet_loss_rate: number;
    total_link_attempts: number;
    successful_transmissions: number;
    broadcast_messages: number;
    direct_messages: number;
    link_reliability: Record<string, number>;
  };
  activity: {
    hourly_distribution: Record<string, number>;
    peak_hours: number[];
    total_active_hours: number;
    messages_per_hour_avg: number;
  };
  alerts: Array<{
    level: 'info' | 'warning' | 'critical';
    type: string;
    message: string;
  }>;
}

export const MetricsDashboard = () => {
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchMetrics = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/metrics');
      if (!response.ok) throw new Error('Failed to fetch metrics');
      const data = await response.json();
      setMetrics(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();

    if (autoRefresh) {
      const interval = setInterval(fetchMetrics, 10000); // Refresh every 10 seconds
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-600 rounded-lg p-4 text-red-400">
        <AlertCircle className="h-5 w-5 inline mr-2" />
        {error}
      </div>
    );
  }

  if (!metrics) return null;

  const getHealthColor = (score: number) => {
    if (score >= 80) return 'text-green-500';
    if (score >= 60) return 'text-yellow-500';
    if (score >= 40) return 'text-orange-500';
    return 'text-red-500';
  };

  const getAlertIcon = (level: string) => {
    switch (level) {
      case 'critical': return <XCircle className="h-4 w-4 text-red-500" />;
      case 'warning': return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      default: return <AlertCircle className="h-4 w-4 text-blue-500" />;
    }
  };

  return (
    <div className="p-4 bg-gray-900 text-gray-100 overflow-auto h-full">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Activity className="h-6 w-6 text-cyan-500" />
          Network Metrics Dashboard
        </h2>
        <button
          onClick={() => setAutoRefresh(!autoRefresh)}
          className={`px-3 py-1 rounded text-sm ${autoRefresh ? 'bg-green-600' : 'bg-gray-700'}`}
        >
          {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
        </button>
      </div>

      {/* Alerts Section */}
      {metrics.alerts && metrics.alerts.length > 0 && (
        <div className="mb-6 space-y-2">
          {metrics.alerts.map((alert, idx) => (
            <div key={idx} className="flex items-center gap-2 p-2 bg-gray-800 rounded border border-gray-700">
              {getAlertIcon(alert.level)}
              <span className="text-sm">{alert.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Main Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {/* Network Health */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-sm">Network Health</span>
            <Network className="h-4 w-4 text-gray-400" />
          </div>
          <div className={`text-3xl font-bold ${getHealthColor(metrics.summary.network_health_score)}`}>
            {Math.round(metrics.summary.network_health_score)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {metrics.summary.network_health_score >= 80 ? 'Excellent' :
             metrics.summary.network_health_score >= 60 ? 'Good' :
             metrics.summary.network_health_score >= 40 ? 'Fair' : 'Poor'}
          </div>
        </div>

        {/* Active Nodes */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-sm">Active Nodes</span>
            <Users className="h-4 w-4 text-gray-400" />
          </div>
          <div className="text-3xl font-bold text-cyan-400">
            {metrics.summary.active_nodes}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            of {metrics.summary.total_nodes} total
          </div>
        </div>

        {/* Message Rate */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-sm">Message Rate</span>
            <MessageSquare className="h-4 w-4 text-gray-400" />
          </div>
          <div className="text-3xl font-bold text-purple-400">
            {metrics.communication.messages_per_minute.toFixed(1)}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            msgs/min ({metrics.communication.messages_last_hour} last hour)
          </div>
        </div>

        {/* Signal Quality */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-sm">Avg Signal</span>
            <Wifi className="h-4 w-4 text-gray-400" />
          </div>
          <div className="text-3xl font-bold text-green-400">
            {metrics.performance.average_rssi ? `${metrics.performance.average_rssi.toFixed(0)}` : 'N/A'}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            dBm ({metrics.performance.average_snr ? `SNR ${metrics.performance.average_snr.toFixed(1)}` : 'No SNR'})
          </div>
        </div>
      </div>

      {/* Detailed Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Topology Analysis */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-cyan-500" />
            Network Topology
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">Connected Components</span>
              <span className={metrics.topology.connected_components > 1 ? 'text-yellow-500' : 'text-green-500'}>
                {metrics.topology.connected_components}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Network Diameter</span>
              <span>{metrics.topology.network_diameter} hops</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Average Node Degree</span>
              <span>{metrics.topology.average_degree.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Clustering Coefficient</span>
              <span>{(metrics.topology.clustering_coefficient * 100).toFixed(1)}%</span>
            </div>
            {metrics.topology.critical_nodes.length > 0 && (
              <div className="mt-2 pt-2 border-t border-gray-700">
                <span className="text-yellow-500 text-xs">Critical nodes: {metrics.topology.critical_nodes.slice(0, 3).join(', ')}</span>
              </div>
            )}
          </div>
        </div>

        {/* Battery Status */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <Battery className="h-5 w-5 text-cyan-500" />
            Battery Status
          </h3>
          <div className="space-y-2 text-sm">
            {metrics.node_categories.by_battery_status.critical.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-red-500">Critical (&lt;20%)</span>
                <span className="text-xs text-gray-400">
                  {metrics.node_categories.by_battery_status.critical.join(', ')}
                </span>
              </div>
            )}
            {metrics.node_categories.by_battery_status.low.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-orange-500">Low (20-40%)</span>
                <span className="text-xs text-gray-400">
                  {metrics.node_categories.by_battery_status.low.slice(0, 3).join(', ')}
                  {metrics.node_categories.by_battery_status.low.length > 3 && ` +${metrics.node_categories.by_battery_status.low.length - 3}`}
                </span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-gray-400">Good (70-100%)</span>
              <span className="text-green-500">{metrics.node_categories.by_battery_status.good.length} nodes</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">External Power</span>
              <span className="text-blue-500">{metrics.node_categories.by_battery_status.external.length} nodes</span>
            </div>
          </div>
        </div>

        {/* Signal Quality Distribution */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <Radio className="h-5 w-5 text-cyan-500" />
            Signal Quality
          </h3>
          <div className="space-y-2">
            {Object.entries(metrics.performance.signal_quality_distribution || {}).map(([quality, count]) => (
              <div key={quality} className="flex items-center gap-2">
                <span className="text-gray-400 capitalize w-20 text-sm">{quality}</span>
                <div className="flex-1 bg-gray-700 rounded-full h-4 relative">
                  <div
                    className={`h-4 rounded-full ${
                      quality === 'excellent' ? 'bg-green-500' :
                      quality === 'good' ? 'bg-yellow-500' :
                      quality === 'fair' ? 'bg-orange-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${(count / metrics.summary.active_nodes) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-gray-400 w-8">{count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Most Active Nodes */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-cyan-500" />
            Most Active Nodes
          </h3>
          <div className="space-y-2 text-sm">
            {Object.entries(metrics.communication.most_active_nodes).map(([node, count]) => (
              <div key={node} className="flex justify-between">
                <span className="text-gray-400">{node}</span>
                <span className="text-cyan-400">{count} msgs</span>
              </div>
            ))}
          </div>
        </div>

        {/* Reliability Metrics */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-cyan-500" />
            Reliability
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">Packet Loss Rate</span>
              <span className={metrics.reliability.estimated_packet_loss_rate > 0.1 ? 'text-yellow-500' : 'text-green-500'}>
                {(metrics.reliability.estimated_packet_loss_rate * 100).toFixed(1)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Successful Transmissions</span>
              <span>{metrics.reliability.successful_transmissions}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Broadcast Messages</span>
              <span>{metrics.reliability.broadcast_messages}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Direct Messages</span>
              <span>{metrics.reliability.direct_messages}</span>
            </div>
          </div>
        </div>

        {/* Activity Patterns */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <Clock className="h-5 w-5 text-cyan-500" />
            Activity Patterns
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">Peak Hours</span>
              <span>{metrics.activity.peak_hours.map(h => `${h}:00`).join(', ')}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Active Hours</span>
              <span>{metrics.activity.total_active_hours}/24</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Avg Messages/Hour</span>
              <span>{metrics.activity.messages_per_hour_avg.toFixed(1)}</span>
            </div>
          </div>
          {/* Mini hourly chart */}
          <div className="mt-3 flex items-end gap-1 h-12">
            {Array.from({ length: 24 }, (_, i) => {
              const count = metrics.activity.hourly_distribution[i] || 0;
              const maxCount = Math.max(...Object.values(metrics.activity.hourly_distribution));
              const height = maxCount > 0 ? (count / maxCount) * 100 : 0;
              return (
                <div
                  key={i}
                  className="flex-1 bg-cyan-600 rounded-t"
                  style={{ height: `${height}%` }}
                  title={`${i}:00 - ${count} msgs`}
                />
              );
            })}
          </div>
          <div className="flex justify-between text-[10px] text-gray-500 mt-1">
            <span>00:00</span>
            <span>12:00</span>
            <span>23:00</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MetricsDashboard;