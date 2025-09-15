from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List, Dict, Any, Optional
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from backend.database import Database
from backend.meshtastic_connector import MeshtasticConnector
from backend.models import (
    NodeInfo, MeshPacket, TextMessage, NetworkLink, 
    Session, WebSocketMessage
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Meshtastic Visualizer", version="1.0.0")

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
class AppState:
    def __init__(self):
        self.db: Optional[Database] = None
        self.meshtastic: Optional[MeshtasticConnector] = None
        self.websocket_clients: List[WebSocket] = []
        self.current_session: Optional[Session] = None
        self.live_nodes: Dict[str, NodeInfo] = {}
        self.live_messages: List[TextMessage] = []
        self.network_links: Dict[str, NetworkLink] = {}
        # Server features
        self.startup_time: datetime = datetime.now()
        self.command_last_seen: Dict[str, float] = {}
        self.env_by_node: Dict[str, Any] = {}
        self.test_channel_index: Optional[int] = None
        self.auto_reply_times: list[float] = []
        self.auto_replies_enabled: bool = True
        self.broadcast_recent: Dict[str, float] = {}

state = AppState()

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    # Initialize database
    state.db = Database()
    await state.db.initialize()
    
    # Start new session
    session_id = await state.db.start_session()
    state.current_session = await state.db.get_active_session()
    logger.info(f"Started new session: {session_id}")
    
    # Initialize Meshtastic connector
    state.meshtastic = MeshtasticConnector(on_data_callback=process_meshtastic_data)
    
    # Auto-connect to device (will try to find RAK 4631)
    if state.meshtastic.connect():
        logger.info("Connected to Meshtastic device")
    else:
        logger.warning("Failed to auto-connect to Meshtastic device")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if state.meshtastic:
        state.meshtastic.disconnect()
    
    if state.db:
        await state.db.end_session()

async def process_meshtastic_data(data: Dict[str, Any]):
    """Process data from Meshtastic device and update all connected clients"""
    try:
        logger.info(f"📥 Backend processing: {data['type']} for {data.get('node_id', data.get('node', {}).get('id', 'unknown'))}")
        
        # Process based on data type
        if data["type"] == "node_info":
            await handle_node_info(data)
        elif data["type"] == "text_message":
            await handle_text_message(data)
        elif data["type"] == "position_update":
            await handle_position_update(data)
        elif data["type"] == "telemetry":
            await handle_telemetry(data)
        elif data["type"] == "network_link":
            await handle_network_link(data)
        elif data["type"] == "mesh_packet":
            await handle_mesh_packet(data)
        
        # Broadcast to all WebSocket clients with simple dedupe window
        # Clean data for JSON serialization
        clean_data = json.loads(json.dumps(data, default=str))
        # Build a lightweight dedupe key by type
        from time import time
        now = time()
        ttl = 2.0
        key = None
        try:
            t = data.get('type')
            if t == 'text_message':
                key = f"tm:{data.get('from_id')}:{data.get('to_id')}:{data.get('message')}:{int(datetime.fromisoformat(str(data.get('timestamp'))).timestamp())}"
            elif t == 'mesh_packet':
                key = f"mp:{data.get('from_id')}:{data.get('to_id')}:{data.get('packet_type')}:{int(datetime.fromisoformat(str(data.get('timestamp'))).timestamp())}"
            elif t == 'node_info':
                node = data.get('node', {})
                key = f"ni:{node.get('id')}:{str(data.get('timestamp'))}"
            elif t == 'position_update':
                key = f"pos:{data.get('node_id')}:{data.get('latitude')}:{data.get('longitude')}:{str(data.get('timestamp'))}"
            elif t == 'telemetry':
                key = f"tel:{data.get('node_id')}:{str(data.get('timestamp'))}"
            else:
                key = f"other:{t}:{str(data.get('timestamp'))}"
        except Exception:
            key = None
        # purge old
        try:
            state.broadcast_recent = {k:v for k,v in state.broadcast_recent.items() if (now - v) < ttl}
        except Exception:
            state.broadcast_recent = {}
        if key and key in state.broadcast_recent:
            logger.info(f"   ⏭️  Suppressed duplicate {data['type']} event")
        else:
            if key:
                state.broadcast_recent[key] = now
            message = WebSocketMessage(
                type=data["type"],
                data=clean_data,
                timestamp=datetime.now()
            )
            logger.info(f"   📡 Broadcasting {data['type']} to {len(state.websocket_clients)} WebSocket clients")
            await broadcast_to_clients(message.dict())
        
    except Exception as e:
        logger.error(f"Error processing Meshtastic data: {e}")

async def handle_node_info(data: Dict):
    """Handle node information update"""
    node_data = data["node"]
    logger.info(f"   Processing node_info: {node_data['id'][:8]} = {node_data.get('short_name', 'Unknown')}")
    
    # Calculate signal quality based on RSSI
    rssi = data.get("rssi")
    signal_quality = None
    if rssi:
        if rssi > -75:
            signal_quality = "excellent"
        elif rssi > -85:
            signal_quality = "good"
        elif rssi > -95:
            signal_quality = "weak"
        else:
            signal_quality = "poor"
    
    node = NodeInfo(
        id=node_data["id"],
        short_name=node_data.get("short_name", f"Node-{node_data['id']}"),
        long_name=node_data.get("long_name"),
        hardware_model=node_data.get("hardware_model"),
        role=node_data.get("role", "CLIENT"),
        battery_level=node_data.get("battery_level"),
        voltage=node_data.get("voltage"),
        rssi=rssi,
        snr=data.get("snr"),
        hop_count=data.get("hop_count", 0),
        signal_quality=signal_quality,
        last_heard=data["timestamp"]
    )
    
    # Update live state
    state.live_nodes[node.id] = node
    logger.info(f"   ✅ Added to live_nodes: {node.id[:8]}, total nodes: {len(state.live_nodes)}")
    
    # Save to database
    await state.db.upsert_node(node)

async def handle_text_message(data: Dict):
    """Handle text message"""
    message = TextMessage(
        from_id=data["from_id"],
        from_name=data["from_name"],
        to_id=data["to_id"],
        to_name=data["to_name"],
        message=data["message"],
        timestamp=data["timestamp"],
        rssi=data.get("rssi"),
        snr=data.get("snr"),
        hop_count=data.get("hop_count", 0),
        channel=data.get("channel")
    )
    
    # Update live state (keep last 100 messages)
    state.live_messages.append(message)
    if len(state.live_messages) > 100:
        state.live_messages = state.live_messages[-100:]
    
    # Save to database
    await state.db.save_message(message)

    # Update hop/signal on sender node when available so UI can show correct hops
    try:
        sender_id = message.from_id
        rssi = data.get("rssi")
        snr = data.get("snr")
        hops = data.get("hop_count")
        now_ts = message.timestamp
        if sender_id:
            if sender_id in state.live_nodes:
                node = state.live_nodes[sender_id]
            else:
                node = NodeInfo(
                    id=sender_id,
                    short_name=f"Node-{sender_id[:8]}",
                    last_heard=now_ts,
                    is_online=True,
                    hop_count=999
                )
                state.live_nodes[sender_id] = node

            if hops is not None:
                node.hop_count = hops
            if rssi is not None:
                node.rssi = rssi
                # Recalculate signal quality
                if rssi > -75:
                    node.signal_quality = "excellent"
                elif rssi > -85:
                    node.signal_quality = "good"
                elif rssi > -95:
                    node.signal_quality = "weak"
                else:
                    node.signal_quality = "poor"
            if snr is not None:
                node.snr = snr
            node.last_heard = now_ts
            await state.db.upsert_node(node)
            # Notify clients so UI can refresh hop badges
            await broadcast_to_clients({
                "type": "node_info",
                "data": {"node": node.dict(), "hop_count": node.hop_count},
                "timestamp": now_ts
            })
    except Exception as e:
        logger.error(f"Failed to update node from text_message: {e}")

    # After persistence and node update, consider server commands
    try:
        await maybe_handle_server_command(message)
    except Exception as e:
        logger.error(f"Command handling error: {e}")

async def maybe_handle_server_command(message: TextMessage):
    """Process incoming text commands sent directly to our local node.
    Security: rate limit per (sender, command) and ignore broadcasts.
    Supported: PING, INFO, HELP, WEATHER
    """
    # Preconditions
    if not state.meshtastic or not state.meshtastic.connected:
        return
    if not state.auto_replies_enabled:
        logger.info("Auto replies disabled; ignoring DM command")
        return
    local_id = state.meshtastic.local_node_id
    if not local_id:
        return
    # Ignore broadcasts and messages not directed to us
    to_id = str(message.to_id)
    if to_id in ("4294967295", "^all"):
        return
    if to_id != str(local_id):
        return
    # Ignore our own messages just in case
    if str(message.from_id) == str(local_id):
        return

    # Parse command
    text = (message.message or "").strip()
    if not text:
        return
    text_upper = text.upper()
    # Normalize to a simple command token
    cmd = None
    if text_upper.startswith("PING") or text_upper.startswith("ECHO"):
        cmd = "PING"
    elif text_upper.startswith("INFO"):
        cmd = "INFO"
    elif text_upper.startswith("HELP") or text_upper == "?":
        cmd = "HELP"
    elif text_upper.startswith("WEATHER"):
        cmd = "WEATHER"
    elif text_upper.startswith("UPTIME"):
        cmd = "UPTIME"
    elif text_upper.startswith("NODES"):
        cmd = "NODES"
    elif text_upper.startswith("NEIGHBORS") or text_upper.startswith("NEIGHBOURS"):
        cmd = "NEIGHBORS"
    else:
        return  # Not a recognized command

    # Rate limit per sender+command
    import time
    key = f"{message.from_id}:{cmd}"
    now = time.time()
    # Basic per-command cooldowns
    if cmd == "PING":
        min_interval = 5.0
    elif cmd == "INFO":
        min_interval = 15.0
    elif cmd == "HELP":
        min_interval = 10.0
    elif cmd == "WEATHER":
        min_interval = 30.0
    elif cmd in ("UPTIME", "NODES", "NEIGHBORS"):
        min_interval = 10.0
    else:
        min_interval = 15.0
    last = state.command_last_seen.get(key, 0)
    if (now - last) < min_interval:
        logger.info(f"Rate-limited {cmd} from {message.from_id}")
        return
    state.command_last_seen[key] = now

    # Global budget: cap auto replies in a 60s window to prevent mesh spam
    try:
        window = 60.0
        capacity = 20  # max auto replies per minute
        state.auto_reply_times = [t for t in state.auto_reply_times if (now - t) < window]
        if len(state.auto_reply_times) >= capacity:
            logger.warning("Global auto-reply rate limit reached; dropping reply")
            return
        state.auto_reply_times.append(now)
    except Exception:
        pass

    # Prepare replies
    if cmd == "PING":
        hops = message.hop_count
        if hops is None:
            hop_phrase = "an unknown number of hops"
        elif hops == 1:
            hop_phrase = "1 hop"
        else:
            hop_phrase = f"{hops} hops"
        reply = f"Acknowledge, you are {hop_phrase} away."
        # Send reply on the same channel if we know it, else default
        ch = message.channel if hasattr(message, 'channel') else None
        state.meshtastic.send_text(reply, destination=str(message.from_id), channel_index=ch)
        return

    if cmd == "INFO":
        # Compose concise network info
        nodes = list(state.live_nodes.values())
        total = len(nodes)
        direct = sum(1 for n in nodes if n.hop_count == 1)
        multi = sum(1 for n in nodes if (n.hop_count or 0) >= 2 and (n.hop_count or 999) < 999)
        # Uptime
        delta = datetime.now() - state.startup_time
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        minutes, _ = divmod(rem, 60)
        uptime = (f"{days}d " if days else "") + (f"{hours}h " if hours else "") + (f"{minutes}m" if minutes or (not days and not hours) else "")
        # Local node id shorthand
        my_id = str(local_id)
        # Compose message (keep under ~200 chars)
        reply = (
            f"Nodes: {total} (Direct {direct}, Multi {multi}). "
            f"Uptime: {uptime}. MyID: {my_id}."
        )
        try:
            ch = message.channel if hasattr(message, 'channel') else None
            state.meshtastic.send_text(reply, destination=str(message.from_id), channel_index=ch)
        except Exception as e:
            logger.error(f"Failed to send INFO reply: {e}")
        return

    if cmd == "HELP":
        reply = "Commands: PING, INFO, WEATHER. Send as direct message."
        try:
            ch = message.channel if hasattr(message, 'channel') else None
            state.meshtastic.send_text(reply, destination=str(message.from_id), channel_index=ch)
        except Exception as e:
            logger.error(f"Failed to send HELP reply: {e}")
        return

    if cmd == "WEATHER":
        # Prioritize local node environment if available
        my_id = str(local_id)
        env = state.env_by_node.get(my_id)
        source = "local"
        if not env:
            # Fallback to any node with env metrics (prefer direct neighbors)
            candidate_id = None
            for n in state.live_nodes.values():
                if n.hop_count == 1 and n.id in state.env_by_node:
                    candidate_id = n.id
                    break
            if not candidate_id:
                for n in state.live_nodes.values():
                    if n.id in state.env_by_node:
                        candidate_id = n.id
                        break
            if candidate_id:
                env = state.env_by_node.get(candidate_id)
                source = candidate_id[:8]

        if not env:
            reply = "Weather: no environmental telemetry available."
            ch = message.channel if hasattr(message, 'channel') else None
            state.meshtastic.send_text(reply, destination=str(message.from_id), channel_index=ch)
            return

        # Format values concisely
        t = env.get("temperature")
        h = env.get("humidity")
        p = env.get("pressure")
        parts = []
        if isinstance(t, (int, float)):
            parts.append(f"T={t:.1f}°C")
        if isinstance(h, (int, float)):
            parts.append(f"RH={h:.0f}%")
        if isinstance(p, (int, float)):
            parts.append(f"P={p:.0f}hPa")
        reply = ("Weather (" + source + "): " + ", ".join(parts)) if parts else "Weather: telemetry present but no values."
        try:
            ch = message.channel if hasattr(message, 'channel') else None
            state.meshtastic.send_text(reply, destination=str(message.from_id), channel_index=ch)
        except Exception as e:
            logger.error(f"Failed to send WEATHER reply: {e}")
        return

    if cmd == "UPTIME":
        delta = datetime.now() - state.startup_time
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        minutes, _ = divmod(rem, 60)
        uptime = (f"{days}d " if days else "") + (f"{hours}h " if hours else "") + (f"{minutes}m" if minutes or (not days and not hours) else "")
        reply = f"Uptime: {uptime}".strip()
        try:
            ch = message.channel if hasattr(message, 'channel') else None
            state.meshtastic.send_text(reply, destination=str(message.from_id), channel_index=ch)
        except Exception as e:
            logger.error(f"Failed to send UPTIME reply: {e}")
        return

    if cmd == "NODES":
        nodes = list(state.live_nodes.values())
        total = len(nodes)
        direct = sum(1 for n in nodes if n.hop_count == 1)
        multi = sum(1 for n in nodes if (n.hop_count or 0) >= 2 and (n.hop_count or 999) < 999)
        reply = f"Nodes: {total} (Direct {direct}, Multi {multi})."
        try:
            ch = message.channel if hasattr(message, 'channel') else None
            state.meshtastic.send_text(reply, destination=str(message.from_id), channel_index=ch)
        except Exception as e:
            logger.error(f"Failed to send NODES reply: {e}")
        return

    if cmd == "NEIGHBORS":
        neighbors = [n for n in state.live_nodes.values() if n.hop_count == 1]
        count = len(neighbors)
        # show up to 5 names
        def disp(n: NodeInfo):
            return (n.short_name or n.long_name or n.id)[:12]
        names = ", ".join(disp(n) for n in neighbors[:5])
        tail = "" if count <= 5 else f" (+{count-5} more)"
        reply = f"Neighbors: {count}" + (f" [{names}]{tail}" if count else "")
        try:
            ch = message.channel if hasattr(message, 'channel') else None
            state.meshtastic.send_text(reply, destination=str(message.from_id), channel_index=ch)
        except Exception as e:
            logger.error(f"Failed to send NEIGHBORS reply: {e}")
        return

async def handle_position_update(data: Dict):
    """Handle position update"""
    node_id = data["node_id"]
    logger.info(f"   Processing position: {node_id[:8]} lat={data.get('latitude')}, lon={data.get('longitude')}")
    
    # Update node position if it exists
    if node_id in state.live_nodes:
        state.live_nodes[node_id].latitude = data.get("latitude")
        state.live_nodes[node_id].longitude = data.get("longitude")
        state.live_nodes[node_id].altitude = data.get("altitude")
        state.live_nodes[node_id].last_heard = data["timestamp"]
        logger.info(f"   ✅ Updated position for existing node: {node_id[:8]}")
        
        await state.db.upsert_node(state.live_nodes[node_id])
    else:
        # Create a minimal node so we can display it on the map
        logger.info(f"   ➕ Creating node from position update: {node_id[:8]}")
        node = NodeInfo(
            id=node_id,
            short_name=f"Node-{node_id[:8]}",
            long_name=None,
            hardware_model=None,
            role="CLIENT",
            battery_level=None,
            voltage=None,
            rssi=None,
            snr=None,
            hop_count=999,
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            altitude=data.get("altitude"),
            last_heard=data["timestamp"],
            is_online=True,
            signal_quality=None
        )
        state.live_nodes[node_id] = node
        logger.info(f"   ✅ Added to live_nodes from position: {node_id[:8]}, total nodes: {len(state.live_nodes)}")
        await state.db.upsert_node(node)
        # Also broadcast a node_info so clients create this node immediately
        await broadcast_to_clients({
            "type": "node_info",
            "data": {"node": node.dict(), "hop_count": node.hop_count},
            "timestamp": datetime.now()
        })

async def handle_telemetry(data: Dict):
    """Handle telemetry update"""
    node_id = data["node_id"]
    device_metrics = data.get("device_metrics", {})
    logger.info(f"   Processing telemetry: {node_id[:8]} battery={device_metrics.get('batteryLevel')}%")
    
    # Update node telemetry if it exists
    if node_id in state.live_nodes:
        node = state.live_nodes[node_id]
        node.battery_level = device_metrics.get("batteryLevel")
        node.voltage = device_metrics.get("voltage")
        node.last_heard = data["timestamp"]
        
        # Update hop count and signal info if available
        if data.get("hop_count") is not None:
            node.hop_count = data.get("hop_count")
        if data.get("rssi") is not None:
            node.rssi = data.get("rssi")
            # Recalculate signal quality
            if node.rssi > -75:
                node.signal_quality = "excellent"
            elif node.rssi > -85:
                node.signal_quality = "good"
            elif node.rssi > -95:
                node.signal_quality = "weak"
            else:
                node.signal_quality = "poor"
        if data.get("snr") is not None:
            node.snr = data.get("snr")
            
        logger.info(f"   ✅ Updated existing node: {node_id[:8]}")
        
        await state.db.upsert_node(node)
    else:
        # Create minimal node entry with hop count and signal info
        logger.info(f"   ⚠️ Creating new node from telemetry: {node_id[:8]}")
        
        # Calculate signal quality based on RSSI
        rssi = data.get("rssi")
        signal_quality = None
        if rssi:
            if rssi > -75:
                signal_quality = "excellent"
            elif rssi > -85:
                signal_quality = "good"
            elif rssi > -95:
                signal_quality = "weak"
            else:
                signal_quality = "poor"
        
        node = NodeInfo(
            id=node_id,
            short_name=f"Node-{node_id[:8]}",
            battery_level=device_metrics.get("batteryLevel"),
            voltage=device_metrics.get("voltage"),
            rssi=rssi,
            snr=data.get("snr"),
            hop_count=data.get("hop_count", 999),  # Use 999 for unknown
            signal_quality=signal_quality,
            last_heard=data["timestamp"]
        )
        state.live_nodes[node_id] = node
        logger.info(f"   ✅ Added to live_nodes: {node_id[:8]}, total nodes: {len(state.live_nodes)}")
        await state.db.upsert_node(node)

    # Cache environment metrics for quick WEATHER responses
    try:
        env = data.get("environment_metrics") or {}
        if isinstance(env, dict):
            norm: Dict[str, Any] = {}
            if env.get("temperature") is not None:
                norm["temperature"] = env.get("temperature")
            if env.get("relativeHumidity") is not None:
                norm["humidity"] = env.get("relativeHumidity")
            if env.get("barometricPressure") is not None:
                norm["pressure"] = env.get("barometricPressure")
            if norm:
                norm["timestamp"] = data.get("timestamp")
                state.env_by_node[node_id] = norm
    except Exception as e:
        logger.error(f"Failed to cache environment metrics: {e}")

async def handle_network_link(data: Dict):
    """Handle network link update"""
    link = NetworkLink(
        from_id=data["from_id"],
        to_id=data["to_id"],
        rssi=data.get("rssi"),
        snr=data.get("snr"),
        last_seen=data["timestamp"],
        is_direct=data.get("is_direct", True)
    )
    
    # Update live state
    link_key = f"{link.from_id}-{link.to_id}"
    state.network_links[link_key] = link
    
    # Save to database
    await state.db.update_network_link(link)

async def handle_mesh_packet(data: Dict):
    """Handle generic mesh packet"""
    packet = MeshPacket(
        from_id=data["from_id"],
        to_id=data["to_id"],
        packet_type=data["packet_type"],
        payload=data.get("payload"),
        rssi=data.get("rssi"),
        snr=data.get("snr"),
        hop_count=data.get("hop_count", 0),
        channel=data.get("channel", 0),
        timestamp=data["timestamp"]
    )
    
    await state.db.save_packet(packet)

    # Update sender node hop/signal data when available
    try:
        sender_id = packet.from_id
        rssi = data.get("rssi")
        snr = data.get("snr")
        hops = data.get("hop_count")
        now_ts = packet.timestamp
        if sender_id:
            if sender_id in state.live_nodes:
                node = state.live_nodes[sender_id]
            else:
                node = NodeInfo(
                    id=sender_id,
                    short_name=f"Node-{sender_id[:8]}",
                    last_heard=now_ts,
                    is_online=True,
                    hop_count=999
                )
                state.live_nodes[sender_id] = node

            if hops is not None:
                node.hop_count = hops
            if rssi is not None:
                node.rssi = rssi
                if rssi > -75:
                    node.signal_quality = "excellent"
                elif rssi > -85:
                    node.signal_quality = "good"
                elif rssi > -95:
                    node.signal_quality = "weak"
                else:
                    node.signal_quality = "poor"
            if snr is not None:
                node.snr = snr
            node.last_heard = now_ts
            await state.db.upsert_node(node)
            await broadcast_to_clients({
                "type": "node_info",
                "data": {"node": node.dict(), "hop_count": node.hop_count},
                "timestamp": now_ts
            })
    except Exception as e:
        logger.error(f"Failed to update node from mesh_packet: {e}")

async def broadcast_to_clients(message: Dict):
    """Broadcast message to all connected WebSocket clients"""
    if not state.websocket_clients:
        return
    
    disconnected_clients = []
    try:
        # Convert any Pydantic models to dicts
        if hasattr(message.get('data'), 'dict'):
            message['data'] = message['data'].dict()
        message_str = json.dumps(message, default=str)
    except Exception as e:
        logger.error(f"Error serializing message: {e}")
        return
    
    for client in state.websocket_clients:
        try:
            await client.send_text(message_str)
        except:
            disconnected_clients.append(client)
    
    # Remove disconnected clients
    for client in disconnected_clients:
        state.websocket_clients.remove(client)

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection for real-time updates"""
    await websocket.accept()
    state.websocket_clients.append(websocket)
    
    try:
        # Send initial state to new client
        logger.info(f"📱 New WebSocket client connected. Sending initial state with {len(state.live_nodes)} nodes")
        initial_data = {
            "type": "initial_state",
            "data": {
                "session": state.current_session.dict() if state.current_session else None,
                "nodes": [node.dict() for node in state.live_nodes.values()],
                "messages": [msg.dict() for msg in state.live_messages[-50:]],  # Last 50 messages
                "links": [link.dict() for link in state.network_links.values()]
            },
            "timestamp": datetime.now()
        }
        logger.info(f"   Nodes in initial state: {[node.id[:8] for node in state.live_nodes.values()]}")
        await websocket.send_text(json.dumps(initial_data, default=str))
        
        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            # Payloads from the frontend are wrapped as { type, data, timestamp }
            payload = message.get("data") if isinstance(message.get("data"), dict) else message
            
            # Handle client commands
            if message.get("type") == "send_text":
                text = payload.get("text", "")
                destination = payload.get("destination")
                channel_index = payload.get("channel_index")
                try:
                    if isinstance(channel_index, str) and channel_index.isdigit():
                        channel_index = int(channel_index)
                except Exception:
                    channel_index = None
                if state.meshtastic:
                    state.meshtastic.send_text(text, destination, channel_index)
                    
            elif message.get("type") == "request_telemetry":
                node_id = payload.get("node_id")
                if state.meshtastic:
                    state.meshtastic.request_telemetry(node_id)
                    
            elif message.get("type") == "request_position":
                node_id = payload.get("node_id")
                if state.meshtastic:
                    state.meshtastic.request_position(node_id)
                    
    except WebSocketDisconnect:
        if websocket in state.websocket_clients:
            state.websocket_clients.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in state.websocket_clients:
            state.websocket_clients.remove(websocket)

# REST API endpoints
@app.get("/api/session/current")
async def get_current_session():
    """Get current session information"""
    if not state.current_session:
        raise HTTPException(status_code=404, detail="No active session")
    return state.current_session

@app.post("/api/session/new")
async def start_new_session():
    """Start a new session"""
    # End current session
    if state.db:
        await state.db.end_session()
    
    # Clear live state
    state.live_nodes.clear()
    state.live_messages.clear()
    state.network_links.clear()
    
    # Start new session
    session_id = await state.db.start_session()
    state.current_session = await state.db.get_active_session()
    
    # Notify all clients
    await broadcast_to_clients({
        "type": "session_reset",
        "data": {"session": state.current_session.dict()},
        "timestamp": datetime.now()
    })
    
    return state.current_session

@app.get("/api/nodes")
async def get_nodes(active_only: bool = True, since_seconds: int = 300):
    """Get nodes from current session"""
    logger.info(f"📊 API request for nodes. Live nodes in memory: {len(state.live_nodes)}")
    if active_only:
        nodes = await state.db.get_active_nodes(since_seconds)
    else:
        nodes = list(state.live_nodes.values())
    return nodes

@app.get("/api/messages")
async def get_messages(limit: int = 50):
    """Get recent messages"""
    messages = await state.db.get_recent_messages(limit)
    return messages

@app.get("/api/topology")
async def get_topology():
    """Get network topology"""
    links = await state.db.get_network_topology()
    return links

@app.post("/api/device/connect")
async def connect_device(device_path: Optional[str] = None):
    """Connect to Meshtastic device"""
    if not state.meshtastic:
        state.meshtastic = MeshtasticConnector(on_data_callback=process_meshtastic_data)
    
    # If already connected, avoid duplicate subscriptions/connections
    if state.meshtastic.connected:
        return {"status": "connected", "device": device_path or "already-connected"}

    if state.meshtastic.connect(device_path):
        return {"status": "connected", "device": device_path or "auto-detected"}
    else:
        raise HTTPException(status_code=500, detail="Failed to connect to device")

@app.post("/api/device/disconnect")
async def disconnect_device():
    """Disconnect from Meshtastic device"""
    if state.meshtastic:
        state.meshtastic.disconnect()
        return {"status": "disconnected"}
    return {"status": "not_connected"}

@app.get("/api/device/status")
async def get_device_status():
    """Get device connection status"""
    return {
        "connected": state.meshtastic.connected if state.meshtastic else False,
        "local_node_id": state.meshtastic.local_node_id if state.meshtastic else None,
        "test_channel_index": state.test_channel_index,
        "auto_replies_enabled": state.auto_replies_enabled
    }

@app.post("/api/channel/test")
async def set_test_channel(payload: Dict[str, Any]):
    """Set or clear the test/private channel index used for sending when requested.
    Payload: { "index": int | null }
    """
    idx = payload.get("index", None)
    if idx is None:
        state.test_channel_index = None
        return {"status": "cleared"}
    try:
        idx = int(idx)
    except Exception:
        raise HTTPException(status_code=400, detail="index must be integer or null")
    if idx < 0 or idx > 7:
        # Meshtastic supports up to 8 channels typically
        raise HTTPException(status_code=400, detail="index must be between 0 and 7")
    state.test_channel_index = idx
    return {"status": "ok", "test_channel_index": state.test_channel_index}

@app.get("/api/device/channels")
async def get_channels():
    """Return safe channel info (index, name if any, encrypted: bool)."""
    if not state.meshtastic or not state.meshtastic.connected:
        return {"channels": []}
    info = state.meshtastic.get_channels_info()
    return info or {"channels": []}

@app.get("/api/server/settings")
async def get_server_settings():
    return {"auto_replies_enabled": state.auto_replies_enabled}

@app.post("/api/server/settings")
async def set_server_settings(payload: Dict[str, Any]):
    are = payload.get('auto_replies_enabled')
    if are is not None:
        state.auto_replies_enabled = bool(are)
    return {"auto_replies_enabled": state.auto_replies_enabled}

# Serve static files (for production)
# Uncomment when frontend build is ready
# app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
