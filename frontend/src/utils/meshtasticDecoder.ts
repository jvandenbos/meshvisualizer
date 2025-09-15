export interface DecodedPacket {
  id: string;
  timestamp: Date;
  from: string;
  to: string;
  type: string;
  portnum: string;
  payload: any;
  rssi?: number;
  snr?: number;
  hopCount?: number;
  channel?: number;
  encrypted?: boolean;
  raw?: string;
}

export class MeshtasticDecoder {
  static portNumToString(portNum: number): string {
    const portMap: { [key: number]: string } = {
      0: 'UNKNOWN',
      1: 'TEXT_MESSAGE',
      2: 'REMOTE_HARDWARE',
      3: 'POSITION',
      4: 'NODEINFO',
      5: 'ROUTING',
      6: 'ADMIN',
      67: 'TELEMETRY',
      68: 'ZPS',
      69: 'SIMULATOR',
      70: 'TRACEROUTE',
      71: 'NEIGHBORINFO',
      72: 'ATAK_PLUGIN',
      256: 'PRIVATE_APP',
      257: 'ATAK_FORWARDER',
      513: 'IP_TUNNEL',
    };
    return portMap[portNum] || `CUSTOM_${portNum}`;
  }

  static decodePacket(packet: any): DecodedPacket {
    // Try to infer Meshtastic "port" type from explicit port numbers OR high-level event type
    const eventType = packet.type?.toUpperCase?.() || '';
    let portKey: string | null = null;
    if (packet.portnum != null || packet.port_num != null) {
      portKey = this.portNumToString(packet.portnum || packet.port_num);
    } else if (eventType) {
      // Map event types to port categories
      const map: Record<string, string> = {
        TEXT_MESSAGE: 'TEXT_MESSAGE',
        POSITION_UPDATE: 'POSITION',
        POSITION: 'POSITION',
        TELEMETRY: 'TELEMETRY',
        NODE_INFO: 'NODEINFO',
        NODEINFO: 'NODEINFO',
        ROUTING: 'ROUTING',
        ADMIN: 'ADMIN',
      };
      portKey = map[eventType] || 'UNKNOWN';
    }
    // Fallback: sometimes packet.packet_type carries numeric port
    if (!portKey && packet.packet_type != null) {
      if (typeof packet.packet_type === 'number') {
        portKey = this.portNumToString(packet.packet_type);
      } else if (typeof packet.packet_type === 'string') {
        portKey = packet.packet_type.toUpperCase();
      }
    }

    const decoded: DecodedPacket = {
      id: `pkt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(packet.timestamp || Date.now()),
      from: packet.from_id || packet.from || 'unknown',
      to: packet.to_id || packet.to || 'unknown',
      type: packet.packet_type || packet.type || 'UNKNOWN',
      portnum: portKey || 'UNKNOWN',
      payload: packet.payload || {},
      rssi: packet.rssi,
      snr: packet.snr,
      hopCount: packet.hop_count,
      channel: packet.channel,
      encrypted: packet.encrypted || false,
      raw: JSON.stringify(packet, null, 2),
    };

    // Decode specific payload types
    if (decoded.portnum === 'TEXT_MESSAGE' && (packet.payload?.text || packet.message)) {
      decoded.payload = {
        text: packet.payload?.text || packet.message,
        decoded: true,
      };
      if (!decoded.from || decoded.from === 'unknown') decoded.from = packet.from_id || packet.from_name || packet.node_id || 'unknown';
      if (!decoded.to || decoded.to === 'unknown') decoded.to = packet.to_id || packet.to_name || 'broadcast';
    } else if (decoded.portnum === 'POSITION') {
      decoded.payload = {
        latitude: packet.payload?.latitude ?? packet.latitude,
        longitude: packet.payload?.longitude ?? packet.longitude,
        altitude: packet.payload?.altitude ?? packet.altitude,
        time: packet.payload?.time ?? packet.time,
        decoded: true,
      };
      if (!decoded.from || decoded.from === 'unknown') decoded.from = packet.node_id || 'unknown';
      if (!decoded.to || decoded.to === 'unknown') decoded.to = 'broadcast';
    } else if (decoded.portnum === 'TELEMETRY') {
      decoded.payload = {
        battery: packet.payload?.battery_level ?? packet.payload?.batteryLevel ?? packet.device_metrics?.batteryLevel,
        voltage: packet.payload?.voltage ?? packet.device_metrics?.voltage,
        channelUtilization: packet.payload?.channel_utilization ?? packet.device_metrics?.channel_utilization,
        airtime: packet.payload?.air_util_tx ?? packet.device_metrics?.air_util_tx,
        decoded: true,
      };
      if (!decoded.from || decoded.from === 'unknown') decoded.from = packet.node_id || 'unknown';
      if (!decoded.to || decoded.to === 'unknown') decoded.to = 'broadcast';
    } else if (decoded.portnum === 'NODEINFO') {
      decoded.payload = {
        id: packet.payload?.id ?? packet.node?.id ?? packet.id,
        shortName: packet.payload?.short_name ?? packet.node?.short_name,
        longName: packet.payload?.long_name ?? packet.node?.long_name,
        hardware: packet.payload?.hw_model || packet.payload?.hardware_model || packet.node?.hardware_model,
        role: packet.payload?.role ?? packet.node?.role,
        decoded: true,
      };
      if (!decoded.from || decoded.from === 'unknown') decoded.from = packet.node?.id || packet.node_id || 'unknown';
      if (!decoded.to || decoded.to === 'unknown') decoded.to = 'broadcast';
    } else if (decoded.portnum === 'ROUTING') {
      decoded.payload = {
        hopStart: packet.hopStart ?? packet.payload?.hopStart,
        hopLimit: packet.hopLimit ?? packet.payload?.hopLimit,
        via: packet.via ?? packet.payload?.via,
        id: packet.id ?? packet.payload?.id,
        wantAck: packet.wantAck ?? packet.payload?.wantAck,
        acked: packet.acked ?? packet.payload?.acked,
        priority: packet.priority ?? packet.payload?.priority,
        decoded: true,
      };
    } else if (decoded.portnum === 'ADMIN') {
      decoded.payload = {
        command: packet.payload?.command || packet.command,
        param: packet.payload?.param || packet.param,
        target: packet.payload?.target || packet.target,
        value: packet.payload?.value ?? packet.value,
        decoded: true,
      };
    }

    return decoded;
  }

  static getPacketColor(portnum: string): string {
    const colorMap: { [key: string]: string } = {
      'TEXT_MESSAGE': 'text-blue-400',
      'POSITION': 'text-green-400',
      'TELEMETRY': 'text-yellow-400',
      'NODEINFO': 'text-purple-400',
      'ROUTING': 'text-orange-400',
      'ADMIN': 'text-red-400',
    };
    return colorMap[portnum] || 'text-gray-400';
  }

  static toHumanReadable(packet: DecodedPacket): { title: string; fields: Array<{ label: string; value: string }>; } {
    const fields: Array<{ label: string; value: string }> = [];

    switch (packet.portnum) {
      case 'TEXT_MESSAGE':
        fields.push({ label: 'Message', value: packet.payload?.text || '(empty)' });
        break;
      case 'POSITION':
        fields.push({ label: 'Latitude', value: String(packet.payload?.latitude ?? '—') });
        fields.push({ label: 'Longitude', value: String(packet.payload?.longitude ?? '—') });
        if (packet.payload?.altitude !== undefined) fields.push({ label: 'Altitude', value: `${packet.payload.altitude} m` });
        break;
      case 'TELEMETRY':
        if (packet.payload?.battery !== undefined) fields.push({ label: 'Battery', value: `${packet.payload.battery}%` });
        if (packet.payload?.voltage !== undefined) fields.push({ label: 'Voltage', value: `${packet.payload.voltage} V` });
        if (packet.payload?.channelUtilization !== undefined) fields.push({ label: 'Channel Utilization', value: `${packet.payload.channelUtilization}%` });
        if (packet.payload?.airtime !== undefined) fields.push({ label: 'Air Tx', value: `${packet.payload.airtime} ms` });
        break;
      case 'NODEINFO':
        if (packet.payload?.shortName) fields.push({ label: 'Short Name', value: packet.payload.shortName });
        if (packet.payload?.longName) fields.push({ label: 'Long Name', value: packet.payload.longName });
        if (packet.payload?.hardware) fields.push({ label: 'Hardware', value: packet.payload.hardware });
        if (packet.payload?.role) fields.push({ label: 'Role', value: packet.payload.role });
        break;
      case 'ROUTING':
        if (packet.payload?.hopStart !== undefined) fields.push({ label: 'Hop Start', value: String(packet.payload.hopStart) });
        if (packet.payload?.hopLimit !== undefined) fields.push({ label: 'Hop Limit', value: String(packet.payload.hopLimit) });
        if (packet.payload?.via) fields.push({ label: 'Via', value: String(packet.payload.via) });
        if (packet.payload?.id !== undefined) fields.push({ label: 'ID', value: String(packet.payload.id) });
        if (packet.payload?.wantAck !== undefined) fields.push({ label: 'Want Ack', value: String(!!packet.payload.wantAck) });
        if (packet.payload?.acked !== undefined) fields.push({ label: 'Acked', value: String(!!packet.payload.acked) });
        if (packet.payload?.priority !== undefined) fields.push({ label: 'Priority', value: String(packet.payload.priority) });
        break;
      case 'ADMIN':
        if (packet.payload?.command) fields.push({ label: 'Command', value: String(packet.payload.command) });
        if (packet.payload?.param) fields.push({ label: 'Param', value: String(packet.payload.param) });
        if (packet.payload?.target) fields.push({ label: 'Target', value: String(packet.payload.target) });
        if (packet.payload?.value !== undefined) fields.push({ label: 'Value', value: String(packet.payload.value) });
        break;
      default:
        // Fallback to payload JSON
        fields.push({ label: 'Payload', value: JSON.stringify(packet.payload ?? {}, null, 2) });
    }

    return {
      title: packet.portnum,
      fields,
    };
  }
}

export default MeshtasticDecoder;
