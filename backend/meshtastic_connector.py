import meshtastic
import meshtastic.serial_interface
from pubsub import pub
from datetime import datetime
from typing import Optional, Dict, Any, Callable
import asyncio
import time
import logging
from backend.models import NodeInfo, MeshPacket, TextMessage, NetworkLink
from backend.pkc_key_manager import PKCKeyManager
from backend.pkc_key_history import PKCKeyHistory
from backend.hop_count_resolver import get_hop_resolver

logger = logging.getLogger(__name__)

class MeshtasticConnector:
    def __init__(self, on_data_callback: Optional[Callable] = None):
        self.interface: Optional[meshtastic.serial_interface.SerialInterface] = None
        self.connected = False
        self.node_db: Dict[str, NodeInfo] = {}
        self.on_data_callback = on_data_callback
        self.local_node_id: Optional[str] = None
        self.local_node_hex_id: Optional[str] = None  # Hex format for local node
        self._subscribed = False
        # Initialize PKC key manager with conservative settings
        self.pkc_manager = PKCKeyManager(max_retries=2, backoff_minutes=30)
        # Initialize PKC key history tracker
        self.pkc_history = PKCKeyHistory()
        # Initialize hop count resolver
        self.hop_resolver = get_hop_resolver()
        # Channel names mapping
        self.channel_names = {0: "Primary"}  # Default primary channel
        
    def connect(self, device_path: Optional[str] = None) -> bool:
        """Connect to RAK 4631 over USB-C"""
        try:
            # Prevent duplicate subscriptions and reconnects when already connected
            if self.connected and self.interface is not None:
                logger.info("Meshtastic already connected; skipping reconnect")
                return True
            # Set up event handlers
            if not self._subscribed:
                pub.subscribe(self.on_receive, "meshtastic.receive")
                pub.subscribe(self.on_connection, "meshtastic.connection.established")
                pub.subscribe(self.on_connection_lost, "meshtastic.connection.lost")
                self._subscribed = True
            
            # Connect to device
            if device_path:
                self.interface = meshtastic.serial_interface.SerialInterface(devPath=device_path)
            else:
                # Auto-detect RAK 4631
                self.interface = meshtastic.serial_interface.SerialInterface()
            
            self.connected = True
            logger.info(f"Connected to Meshtastic device")
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from device"""
        if self.interface:
            self.interface.close()
            self.connected = False
            logger.info("Disconnected from Meshtastic device")
    
    def on_connection(self, interface, topic=pub.AUTO_TOPIC):
        """Called when connection is established"""
        logger.info("Meshtastic connection established")

        # Update channel names mapping
        try:
            if hasattr(interface, 'channels'):
                channels = interface.channels
                if isinstance(channels, dict):
                    for idx, ch in channels.items():
                        if hasattr(ch, 'settings') and hasattr(ch.settings, 'name'):
                            name = ch.settings.name
                            if name:  # Only update if name is not empty
                                self.channel_names[int(idx)] = name
                                logger.info(f"Channel {idx}: {name}")
                            elif int(idx) == 0:
                                self.channel_names[0] = "Primary"
                            else:
                                self.channel_names[int(idx)] = f"Channel {idx}"
        except Exception as e:
            logger.warning(f"Could not get channel names: {e}")

        # Get device metadata including firmware version
        self.device_metadata = {}
        try:
            # Get firmware version and device info
            if hasattr(interface, 'metadata'):
                self.device_metadata['firmware_version'] = getattr(interface.metadata, 'firmware_version', 'Unknown')
                self.device_metadata['device_state_version'] = getattr(interface.metadata, 'device_state_version', 0)

            # Try to get more device info
            if hasattr(interface, 'myInfo'):
                if hasattr(interface.myInfo, 'firmware_version'):
                    self.device_metadata['firmware_version'] = interface.myInfo.firmware_version
                if hasattr(interface.myInfo, 'region'):
                    self.device_metadata['region'] = interface.myInfo.region
                if hasattr(interface.myInfo, 'hw_model'):
                    self.device_metadata['hw_model'] = interface.myInfo.hw_model

            logger.info(f"Device metadata: {self.device_metadata}")
        except Exception as e:
            logger.warning(f"Could not get device metadata: {e}")

        # Get local node info
        if hasattr(interface, 'myInfo') and interface.myInfo:
            self.local_node_id = str(interface.myInfo.my_node_num)
            self.local_node_hex_id = f"!{int(self.local_node_id):08x}"  # Store hex format with padding
            logger.info(f"Local node ID: {self.local_node_id} (hex: {self.local_node_hex_id})")

            # Set local node for hop resolver
            self.hop_resolver.set_local_node(self.local_node_hex_id)

            # Debug: Check what we have
            if hasattr(interface.myInfo, 'user'):
                user = interface.myInfo.user
                logger.info(f"Local node user info: shortName={getattr(user, 'shortName', 'N/A')}, longName={getattr(user, 'longName', 'N/A')}")
            else:
                logger.warning("No user info in myInfo")

            # Try multiple ways to get local node info
            local_short_name = None
            local_long_name = None
            local_hw_model = "Unknown"

            # Method 1: Try nodes database
            if hasattr(interface, 'nodes') and interface.nodes:
                # Try both decimal and hex node IDs
                hex_id = f"!{int(self.local_node_id):08x}"
                for node_id in [self.local_node_id, hex_id]:
                    if node_id in interface.nodes:
                        local_node = interface.nodes[node_id]
                        if 'user' in local_node:
                            local_user = local_node['user']
                            local_short_name = local_user.get('shortName', local_short_name)
                            local_long_name = local_user.get('longName', local_long_name)
                            local_hw_model = str(local_user.get('hwModel', local_hw_model))
                            logger.info(f"Got local node from nodes DB: {local_short_name} / {local_long_name}")
                            break

            # Method 2: Try to get from nodesByNum
            if not local_short_name and hasattr(interface, 'nodesByNum'):
                try:
                    node_num = int(self.local_node_id)
                    if node_num in interface.nodesByNum:
                        node = interface.nodesByNum[node_num]
                        if 'user' in node:
                            user = node['user']
                            local_short_name = user.get('shortName', local_short_name)
                            local_long_name = user.get('longName', local_long_name)
                            local_hw_model = str(user.get('hwModel', local_hw_model))
                            logger.info(f"Got local node from nodesByNum: {local_short_name} / {local_long_name}")
                except (ValueError, AttributeError) as e:
                    logger.debug(f"Could not get from nodesByNum: {e}")

            # If still no name, log what we have
            if not local_short_name:
                logger.warning(f"Could not get local node name from device, will wait for node_info packet")

            # Create entry for local node with hex ID
            hex_node_id = f"!{int(self.local_node_id):08x}"  # Use 8-digit padding
            self.node_db[hex_node_id] = {
                "id": hex_node_id,
                "short_name": local_short_name,
                "long_name": local_long_name,
                "hardware_model": local_hw_model,
                "role": "CLIENT",
                "hop_count": 0,  # Local node is always 0 hops
                "is_local": True,
                "firmware_version": self.device_metadata.get('firmware_version', 'Unknown'),
                "region": self.device_metadata.get('region', 'Unknown')
            }
            
            # Send local node info to backend if we have a name
            if self.on_data_callback and local_short_name:
                local_node_data = {
                    "type": "node_info",
                    "node": self.node_db[hex_node_id],
                    "hop_count": 0,
                    "timestamp": datetime.now()
                }
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(self.on_data_callback(local_node_data))
                except RuntimeError:
                    asyncio.run(self.on_data_callback(local_node_data))
        
        # Do NOT broadcast anything by default to avoid mesh spam.
        # If an announcement is ever needed, guard with an env flag and send once.
        # Intentionally left disabled.
    
    def on_connection_lost(self, interface, topic=pub.AUTO_TOPIC):
        """Called when connection is lost"""
        logger.warning("Meshtastic connection lost")
        self.connected = False
        
        if self.on_data_callback:
            asyncio.create_task(self.on_data_callback({
                "type": "connection_lost",
                "timestamp": datetime.now()
            }))
    
    def on_receive(self, packet, interface):
        """Process incoming packets in real-time (<100ms)"""
        start_time = time.time()

        try:
            # Check if packet is encrypted (not decoded by Meshtastic library)
            if 'encrypted' in packet and 'decoded' not in packet:
                logger.warning(f"⚠️ Received encrypted packet that couldn't be decoded - likely PKC DM with key issues")
                # Still log it for debugging
                from_id = packet.get('fromId') or packet.get('from')
                to_id = packet.get('toId') or packet.get('to')
                logger.info(f"   Encrypted packet from {from_id} to {to_id}")

                # Process as encrypted DM for visibility
                from_id = self.normalize_id(str(from_id)) if from_id else "unknown"
                to_id = self.normalize_id(str(to_id)) if to_id else "unknown"

                # Check if this is a DM directed at us (not broadcast)
                is_broadcast = to_id in ["broadcast", "^all", "4294967295"]
                is_dm_to_us = to_id == self.local_node_hex_id and not is_broadcast

                if is_dm_to_us:
                    # This is a DM to us that we can't decrypt - likely PKC issue
                    from_name = self.node_db.get(from_id, {}).get('short_name', from_id)
                    logger.warning(f"📨 Failed to decrypt DM from {from_id} ({from_name})")

                    # Record the PKC failure for DMs only
                    self.pkc_history.record_decryption_failure(from_id)

                    # Attempt automatic PKC key refresh
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(
                                self.pkc_manager.refresh_node_key(from_id, from_name)
                            )
                        else:
                            asyncio.run(
                                self.pkc_manager.refresh_node_key(from_id, from_name)
                            )
                    except Exception as e:
                        logger.error(f"Failed to initiate key refresh: {e}")

                    # Get PKC diagnostics for the error message
                    pkc_diagnostics = self.pkc_history.get_diagnostics(from_id)
                    error_message = f"[Encrypted DM - PKC failed] {pkc_diagnostics}"
                elif is_broadcast:
                    # This is an encrypted broadcast - likely channel key issue
                    error_message = f"[Encrypted broadcast - channel key missing]"
                else:
                    # Some other encrypted packet type
                    error_message = f"[Encrypted packet - unknown type]"

                # Send as encrypted message notification (but don't show in UI message feed)
                encrypted_msg_data = {
                    "type": "encrypted_packet",  # Changed from text_message to filter in UI
                    "from_id": from_id,
                    "from_name": self.node_db.get(from_id, {}).get('short_name', from_id),
                    "to_id": to_id,
                    "to_name": self.node_db.get(to_id, {}).get('short_name', to_id),
                    "message": error_message,
                    "timestamp": datetime.now(),
                    "encrypted": True,
                    "rssi": packet.get('rxRssi'),
                    "snr": packet.get('rxSnr'),
                    "hop_count": (packet.get('hopStart', 0) - packet.get('hopLimit', 0)) if packet.get('hopStart', 0) > 0 else None,
                    "channel": packet.get('channel', 0)  # Add channel info
                }

                # Only add PKC info for actual DMs
                if is_dm_to_us:
                    encrypted_msg_data["pkc_info"] = self.pkc_history.get_key_info(from_id)

                if self.on_data_callback:
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(self.on_data_callback(encrypted_msg_data))
                        else:
                            asyncio.run(self.on_data_callback(encrypted_msg_data))
                    except RuntimeError:
                        asyncio.run(self.on_data_callback(encrypted_msg_data))
                return  # Don't process further

            # Extract packet data - handle different packet structures
            packet_dict = packet.get('decoded', packet)

            # Try different fields for from_id
            from_id = packet.get('fromId') or packet.get('from')
            if not from_id and 'fromId' in str(packet):
                # Sometimes it's in the string representation
                from_id = self.local_node_id
            from_id = str(from_id) if from_id else self.local_node_id

            # Normalize from_id to consistent hex format
            from_id = self.normalize_id(from_id)
            
            # Try different fields for to_id
            to_id_raw = packet.get('toId') or packet.get('to') or '^all'
            
            # Log raw packet info
            logger.info(f"📡 Packet from {from_id[:8] if from_id else 'Unknown'} to {to_id_raw[:8] if isinstance(to_id_raw, str) else to_id_raw}")
            # Handle special broadcast IDs
            if to_id_raw == '^all' or str(to_id_raw) == '4294967295':
                to_id = 'broadcast'
            else:
                to_id = str(to_id_raw)
            
            # Process based on packet type
            data = None
            # Determine port consistently (supports numeric and string names)
            port_raw = packet_dict.get('portnum', packet.get('portnum'))
            portnum: int | None = None
            portname: str | None = None
            if isinstance(port_raw, (int, float)):
                try:
                    portnum = int(port_raw)
                except Exception:
                    portnum = None
            elif isinstance(port_raw, str):
                s = port_raw.upper()
                portname = s
                # Map common Meshtastic enum strings to numeric where known
                name_to_num = {
                    'TEXT_MESSAGE_APP': 1,
                    'POSITION_APP': 3,
                    'NODEINFO_APP': 4,
                    'TELEMETRY_APP': 67,
                }
                portnum = name_to_num.get(s)
            
            # Log with correct hop calculation
            hop_count_log = (packet.get('hopStart', 0) - packet.get('hopLimit', 0)) if packet.get('hopStart', 0) > 0 else 0
            rssi_log = packet.get('rxRssi') or packet.get('rx_rssi')
            snr_log = packet.get('rxSnr') or packet.get('rx_snr')
            ptype_str = None
            if portnum == 1:
                ptype_str = 'TEXT_MESSAGE'
            elif portnum == 3:
                ptype_str = 'POSITION'
            elif portnum == 4:
                ptype_str = 'NODEINFO'
            elif portnum == 67:
                ptype_str = 'TELEMETRY'
            else:
                ptype_str = portname or (str(portnum) if portnum is not None else 'UNKNOWN')
            logger.info(f"   Type: {ptype_str}, RSSI: {rssi_log}, SNR: {snr_log}, Hops: {hop_count_log}")
            
            if portnum == 1 or portname == 'TEXT_MESSAGE_APP':  # TEXT_MESSAGE
                # Comprehensive logging for debugging DM issues
                logger.info(f"📨 Processing TEXT_MESSAGE packet")
                logger.info(f"   Full packet keys: {list(packet.keys())}")
                logger.info(f"   Decoded section keys: {list(packet_dict.keys()) if packet_dict else 'No decoded'}")

                # Try multiple methods to extract text
                text_content = None

                # Method 1: Direct in packet
                if 'text' in packet:
                    text_content = packet['text']
                    logger.info(f"   ✅ Found text in packet root: '{text_content}'")
                    packet_dict['text'] = text_content

                # Method 2: In decoded section
                if not text_content and packet_dict and 'text' in packet_dict:
                    text_content = packet_dict['text']
                    logger.info(f"   ✅ Found text in decoded: '{text_content}'")

                # If we successfully decoded a DM, reset any PKC retry counts for this sender
                if text_content and from_id and to_id == self.local_node_hex_id:
                    # Successfully decrypted a DM from this node - reset their retry count
                    self.pkc_manager.reset_node(from_id)
                    logger.info(f"✓ Successfully decrypted DM from {from_id} - reset PKC retry count")

                # Method 3: Check payload field
                if not text_content and packet_dict and 'payload' in packet_dict:
                    payload = packet_dict['payload']
                    logger.info(f"   Payload type: {type(payload)}, repr: {repr(payload)[:100]}")
                    try:
                        if isinstance(payload, bytes):
                            text_content = payload.decode('utf-8', errors='replace')
                            logger.info(f"   ✅ Decoded text from payload bytes: '{text_content}'")
                            packet_dict['text'] = text_content
                        elif isinstance(payload, str):
                            text_content = payload
                            logger.info(f"   ✅ Payload was string: '{text_content}'")
                            packet_dict['text'] = text_content
                    except Exception as e:
                        logger.error(f"   ❌ Failed to decode payload: {e}")

                # Check for encryption issues
                if 'encrypted' in packet:
                    logger.warning(f"   ⚠️ Packet has 'encrypted' field - may indicate decryption failure")
                    if not packet_dict or 'decoded' not in packet:
                        logger.error(f"   ❌ Encrypted packet was NOT decoded - check channel keys!")

                # Final logging
                if text_content:
                    logger.info(f"   💬 Text message: '{text_content[:50]}{'...' if len(text_content) > 50 else ''}' from {from_id[:8]}")
                else:
                    logger.warning(f"   ⚠️ No text content found!")
                    logger.info(f"   Full packet dump: {packet}")
                    logger.info(f"   Decoded dump: {packet_dict}")
                data = self.process_text_message(packet_dict, from_id, to_id)
            elif portnum == 3 or portname == 'POSITION_APP':  # POSITION
                logger.info(f"   📍 Position update from {from_id[:8]}")
                data = self.process_position(packet_dict, from_id)
            elif portnum == 4 or portname == 'NODEINFO_APP':  # NODEINFO
                logger.info(f"   👤 Node info from {from_id[:8]}")
                data = self.process_node_info(packet_dict, from_id)
            elif portnum == 67 or portname == 'TELEMETRY_APP':  # TELEMETRY
                logger.info(f"   📊 Telemetry from {from_id[:8]}")
                data = self.process_telemetry(packet_dict, from_id)
            else:
                data = self.process_generic_packet(packet_dict, from_id, to_id)
            
            # Add common packet info
            if data:
                # Use the enhanced hop resolver for intelligent hop count calculation
                hop_count = self.hop_resolver.calculate_hop_count(packet)

                # Log if we resolved an unknown
                hop_start = packet.get('hopStart', 0)
                if hop_start == 0 and hop_count is not None:
                    logger.debug(f"Hop resolver estimated {hop_count} hops for packet without hopStart")

                data.update({
                    "rssi": packet.get('rxRssi') or packet.get('rx_rssi'),  # Try both camelCase and snake_case
                    "snr": packet.get('rxSnr') or packet.get('rx_snr'),
                    "hop_count": hop_count,
                    "channel": packet.get('channel', 0)
                })
                
                # Update network topology
                if from_id != self.local_node_id:
                    self.update_network_link(from_id, to_id, data)
                
                # Send to callback
                if self.on_data_callback:
                    logger.info(f"   ✅ Sending {data['type']} to backend for node {data.get('node_id', data.get('node', {}).get('id', 'unknown'))}")
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(self.on_data_callback(data))
                        else:
                            asyncio.run(self.on_data_callback(data))
                    except RuntimeError:
                        # If no event loop, create one
                        asyncio.run(self.on_data_callback(data))
            
            # Performance monitoring
            processing_time = (time.time() - start_time) * 1000
            if processing_time > 50:  # Warning if approaching 100ms limit
                logger.warning(f"Packet processing time: {processing_time:.1f}ms")
                
        except Exception as e:
            logger.error(f"Error processing packet: {e}")
    
    def normalize_id(self, node_id: str) -> str:
        """Normalize node ID to consistent 8-digit hex format"""
        if not node_id:
            return node_id

        # Already hex format - ensure padding
        if node_id.startswith('!'):
            hex_part = node_id[1:]
            try:
                decimal_val = int(hex_part, 16)
                return f"!{decimal_val:08x}"
            except (ValueError, TypeError):
                return node_id

        # Convert decimal to hex with padding
        try:
            decimal_id = int(node_id)
            return f"!{decimal_id:08x}"
        except (ValueError, TypeError):
            return node_id

    def process_text_message(self, packet: Dict, from_id: str, to_id: str) -> Dict:
        """Process text message packet"""
        # Normalize IDs
        from_id = self.normalize_id(from_id)
        to_id = self.normalize_id(to_id) if to_id not in ["4294967295", "^all", "broadcast"] else to_id

        message = packet.get('text', '')
        from_name = self.node_db.get(from_id, {}).get('short_name', f"Node-{from_id}")
        to_name = self.node_db.get(to_id, {}).get('short_name', "All" if to_id == "4294967295" else f"Node-{to_id}")
        
        return {
            "type": "text_message",
            "from_id": from_id,
            "from_name": from_name,
            "to_id": to_id,
            "to_name": to_name,
            "message": message,
            "timestamp": datetime.now()
        }
    
    def process_position(self, packet: Dict, from_id: str) -> Dict:
        """Process position packet"""
        # Normalize ID
        from_id = self.normalize_id(from_id)
        position = packet.get('position', {})
        
        # Update node database
        if from_id not in self.node_db:
            self.node_db[from_id] = {}
        
        self.node_db[from_id].update({
            "latitude": position.get('latitudeI', 0) / 1e7 if 'latitudeI' in position else None,
            "longitude": position.get('longitudeI', 0) / 1e7 if 'longitudeI' in position else None,
            "altitude": position.get('altitude', 0)
        })
        
        return {
            "type": "position_update",
            "node_id": from_id,
            "latitude": self.node_db[from_id].get("latitude"),
            "longitude": self.node_db[from_id].get("longitude"),
            "altitude": self.node_db[from_id].get("altitude"),
            "timestamp": datetime.now()
        }
    
    def process_node_info(self, packet: Dict, from_id: str) -> Dict:
        """Process node info packet"""
        user = packet.get('user', {})

        # Update hop resolver with NodeInfo packet
        if from_id:
            hex_from_id = f"!{int(from_id):08x}" if from_id.isdigit() else from_id
            self.hop_resolver.update_from_nodeinfo(hex_from_id, packet)

        # Check for public key in the packet and track it
        if 'publicKey' in user or 'public_key' in user:
            pub_key = user.get('publicKey') or user.get('public_key')
            if pub_key:
                # Convert to bytes if it's a hex string
                if isinstance(pub_key, str):
                    try:
                        pub_key_bytes = bytes.fromhex(pub_key)
                    except:
                        pub_key_bytes = pub_key.encode() if len(pub_key) == 32 else None
                else:
                    pub_key_bytes = pub_key

                if pub_key_bytes and len(pub_key_bytes) == 32:
                    # Update PKC history with the public key
                    hex_from_id = f"!{int(from_id):08x}" if from_id.isdigit() else from_id
                    key_update = self.pkc_history.update_public_key(
                        hex_from_id,
                        pub_key_bytes,
                        user.get('shortName', f"Node-{hex_from_id[:8]}")
                    )
                    if key_update.get("key_changed"):
                        logger.info(f"      🔑 Node public key updated: {key_update['key_hash']} (update #{key_update['update_count']})")
                    else:
                        logger.info(f"      🔑 Node public key confirmed: {key_update['key_hash']}")
                else:
                    logger.info(f"      🔑 Node has invalid public key length: {len(pub_key_bytes) if pub_key_bytes else 0}")

        # Log full user dict to see what fields are available
        logger.debug(f"      Full user data: {user}")

        # Convert to hex ID for consistency
        hex_from_id = f"!{int(from_id):08x}" if from_id.isdigit() else from_id  # Use 8-digit padding

        # Update node database with hex ID
        if hex_from_id not in self.node_db:
            self.node_db[hex_from_id] = {}
        
        # Handle hardware model - convert int to string if needed
        hw_model = user.get('hwModel', 'UNSET')
        if isinstance(hw_model, int):
            # Convert hardware model ID to string
            hw_model = str(hw_model)
        
        # Handle role - convert int to string if needed
        role = user.get('role', 'CLIENT')
        if isinstance(role, int):
            # Map role numbers to role names (based on Meshtastic protobuf)
            role_map = {
                0: 'CLIENT',
                1: 'CLIENT_MUTE', 
                2: 'ROUTER',
                3: 'ROUTER_CLIENT',
                4: 'REPEATER',
                11: 'TRACKER'  # New role type
            }
            role = role_map.get(role, 'CLIENT')
        
        self.node_db[hex_from_id].update({
            "id": hex_from_id,
            "short_name": user.get('shortName', f"Node-{hex_from_id[:8]}"),
            "long_name": user.get('longName', ''),
            "hardware_model": hw_model,
            "role": role,
            "is_licensed": user.get('isLicensed', False)
        })
        
        logger.info(f"      Node DB updated: {hex_from_id[:8]} = {user.get('shortName', 'Unknown')}, role={role}, hw={hw_model}")

        # Clean up decimal ID entry if it exists
        if from_id != hex_from_id and from_id in self.node_db:
            del self.node_db[from_id]

        return {
            "type": "node_info",
            "node": self.node_db[hex_from_id],
            "timestamp": datetime.now()
        }
    
    def process_telemetry(self, packet: Dict, from_id: str) -> Dict:
        """Process telemetry packet"""
        # Normalize ID
        from_id = self.normalize_id(from_id)
        telemetry = packet.get('telemetry', {})
        
        # Device metrics
        device_metrics = telemetry.get('deviceMetrics', {})
        
        # Update node database
        if from_id not in self.node_db:
            self.node_db[from_id] = {}
        
        self.node_db[from_id].update({
            "battery_level": device_metrics.get('batteryLevel'),
            "voltage": device_metrics.get('voltage'),
            "channel_utilization": device_metrics.get('channelUtilization'),
            "air_util_tx": device_metrics.get('airUtilTx'),
            "uptime_seconds": device_metrics.get('uptimeSeconds')
        })
        
        logger.info(f"      Telemetry updated: {from_id[:8]} battery={device_metrics.get('batteryLevel')}%, voltage={device_metrics.get('voltage')}V")
        
        # Environment metrics
        env_metrics = telemetry.get('environmentMetrics', {})
        if env_metrics:
            self.node_db[from_id].update({
                "temperature": env_metrics.get('temperature'),
                "humidity": env_metrics.get('relativeHumidity'),
                "pressure": env_metrics.get('barometricPressure')
            })
        
        return {
            "type": "telemetry",
            "node_id": from_id,
            "device_metrics": device_metrics,
            "environment_metrics": env_metrics,
            "timestamp": datetime.now()
        }
    
    def process_generic_packet(self, packet: Dict, from_id: str, to_id: str) -> Dict:
        """Process generic packet"""
        # Normalize IDs
        from_id = self.normalize_id(from_id)
        to_id = self.normalize_id(to_id) if to_id not in ["4294967295", "^all", "broadcast"] else to_id
        # Only include serializable payload data
        safe_payload = {}
        if isinstance(packet, dict):
            for key, value in packet.items():
                if isinstance(value, (str, int, float, bool, type(None))):
                    safe_payload[key] = value
                elif isinstance(value, (list, dict)):
                    safe_payload[key] = str(value)
        
        return {
            "type": "mesh_packet",
            "from_id": from_id,
            "to_id": to_id,
            "packet_type": packet.get('portnum', 'UNKNOWN'),
            "payload": safe_payload,
            "timestamp": datetime.now()
        }
    
    def update_network_link(self, from_id: str, to_id: str, packet_data: Dict):
        """Update network topology based on packet routing"""
        # Normalize IDs
        from_id = self.normalize_id(from_id)
        to_id = self.normalize_id(to_id) if to_id not in ["4294967295", "^all", "broadcast"] else to_id
        # This is called for each packet to build network topology
        # The actual link data would be sent via callback
        link_data = {
            "type": "network_link",
            "from_id": from_id,
            "to_id": to_id if to_id not in ["4294967295", "^all"] else self.local_node_hex_id if self.local_node_hex_id else "broadcast",  # Broadcast handling
            "rssi": packet_data.get("rssi"),
            "snr": packet_data.get("snr"),
            "is_direct": packet_data.get("hop_count") == 1,  # Direct connections are 1 hop
            "timestamp": datetime.now()
        }
        
        if self.on_data_callback:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.on_data_callback(link_data))
                else:
                    asyncio.run(self.on_data_callback(link_data))
            except RuntimeError:
                asyncio.run(self.on_data_callback(link_data))
    
    def send_text(self, text: str, destination: Optional[str] = None, channel_index: Optional[int] = None) -> bool:
        """Send text message"""
        if not self.interface or not self.connected:
            return False
        
        try:
            if destination:
                if channel_index is not None:
                    try:
                        self.interface.sendText(text, destinationId=destination, channelIndex=channel_index)
                    except TypeError:
                        # Older API compatibility: no channelIndex param
                        self.interface.sendText(text, destinationId=destination)
                else:
                    self.interface.sendText(text, destinationId=destination)
            else:
                if channel_index is not None:
                    try:
                        self.interface.sendText(text, channelIndex=channel_index)
                    except TypeError:
                        self.interface.sendText(text)
                else:
                    self.interface.sendText(text)
            return True
        except Exception as e:
            logger.error(f"Failed to send text: {e}")
            return False
    
    def request_telemetry(self, node_id: Optional[str] = None):
        """Request telemetry from a node"""
        if not self.interface or not self.connected:
            return
        
        try:
            if node_id:
                self.interface.requestTelemetry(destinationId=node_id)
            else:
                self.interface.requestTelemetry()
        except Exception as e:
            logger.error(f"Failed to request telemetry: {e}")
    
    def request_position(self, node_id: Optional[str] = None):
        """Request position from a node"""
        if not self.interface or not self.connected:
            return
        
        try:
            if node_id:
                self.interface.requestPosition(destinationId=node_id)
            else:
                self.interface.requestPosition()
        except Exception as e:
            logger.error(f"Failed to request position: {e}")
    
    def get_node_info(self, node_id: str) -> Optional[Dict]:
        """Get cached node information"""
        return self.node_db.get(node_id)
    
    def get_all_nodes(self) -> Dict[str, Dict]:
        """Get all cached nodes"""
        return self.node_db.copy()

    def get_channels_info(self) -> Optional[Dict[str, Any]]:
        """Return a safe summary of channel info if available.
        Structure: { "channels": [ {"index": int, "name": str|None, "encrypted": bool } ] }
        """
        if not self.interface:
            return None
        info = {"channels": []}
        try:
            chans = getattr(self.interface, 'channels', None)
            if isinstance(chans, dict):
                for idx, ch in chans.items():
                    name = None
                    psk = None
                    try:
                        name = getattr(ch.settings, 'name', None) if hasattr(ch, 'settings') else getattr(ch, 'name', None)
                    except Exception:
                        name = None
                    try:
                        psk = getattr(ch.settings, 'psk', None) if hasattr(ch, 'settings') else getattr(ch, 'psk', None)
                    except Exception:
                        psk = None
                    encrypted = bool(psk)
                    info["channels"].append({"index": int(idx), "name": name, "encrypted": encrypted})
                return info
        except Exception:
            pass
        # Fallback: try radioConfig
        try:
            rc = getattr(self.interface, 'radioConfig', None)
            if rc and hasattr(rc, 'channels'):
                for i, ch in enumerate(rc.channels):
                    name = getattr(ch.settings, 'name', None) if hasattr(ch, 'settings') else None
                    psk = getattr(ch.settings, 'psk', None) if hasattr(ch, 'settings') else None
                    encrypted = bool(psk)
                    info["channels"].append({"index": i, "name": name, "encrypted": encrypted})
                return info
        except Exception:
            return None
        return None
