"""
Mock Meshtastic interface for testing without real hardware.
"""

import asyncio
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
import random


class MockMeshtasticInterface:
    """Mock implementation of Meshtastic interface for testing."""

    def __init__(self, local_node_id: str = "1109198442"):
        self.local_node_id = local_node_id
        self.local_node_hex = f"!{int(local_node_id):08x}"
        self.is_connected = False
        self.nodes = {}
        self.messages = []
        self.on_receive_callback = None
        self.message_queue = asyncio.Queue()

        # Add local node to nodes database
        self.nodes[self.local_node_id] = {
            'user': {
                'id': self.local_node_hex,
                'longName': 'My Node',
                'shortName': 'MyNode',
                'hwModel': 'RAK4631'
            },
            'position': {},
            'deviceMetrics': {
                'batteryLevel': 100,
                'voltage': 4.2
            }
        }

        # Test configuration
        self.myInfo = type('MyInfo', (), {
            'my_node_num': int(self.local_node_id)
        })()

        self.localNode = type('LocalNode', (), {
            'localConfig': type('LocalConfig', (), {
                'device': type('Device', (), {
                    'role': 'CLIENT'
                })()
            })()
        })()

    def connect(self):
        """Simulate connection to device."""
        self.is_connected = True
        return True

    def disconnect(self):
        """Simulate disconnection from device."""
        self.is_connected = False

    def sendText(self, text: str, destinationId: Any = None, channelIndex: int = 0, wantAck: bool = False):
        """Simulate sending a text message."""
        if not self.is_connected:
            raise Exception("Not connected")

        # Convert destination ID to string
        dest_id = str(destinationId) if destinationId else "^all"

        # Create mock packet for the sent message
        packet = {
            'fromId': self.local_node_id,
            'toId': dest_id,
            'decoded': {
                'portnum': 'TEXT_MESSAGE_APP',
                'text': text
            },
            'rxRssi': 0,
            'rxSnr': 0,
            'hopLimit': 3,
            'hopStart': 0,
            'channel': channelIndex
        }

        # Add to message queue for processing
        asyncio.create_task(self.message_queue.put(packet))

        return True

    def sendPosition(self, latitude: float = 48.0, longitude: float = -123.0, altitude: int = 0):
        """Simulate sending position."""
        if not self.is_connected:
            raise Exception("Not connected")

        packet = {
            'fromId': self.local_node_id,
            'toId': '^all',
            'decoded': {
                'portnum': 'POSITION_APP',
                'position': {
                    'latitudeI': int(latitude * 1e7),
                    'longitudeI': int(longitude * 1e7),
                    'altitude': altitude
                }
            }
        }

        asyncio.create_task(self.message_queue.put(packet))
        return True

    async def simulate_incoming_message(self, from_id: str, to_id: str, text: str,
                                       rssi: int = -75, snr: float = 2.5, hop_count: int = 1):
        """Simulate receiving a message from another node."""
        packet = {
            'fromId': from_id,
            'toId': to_id,
            'decoded': {
                'portnum': 'TEXT_MESSAGE_APP',
                'text': text
            },
            'rxRssi': rssi,
            'rxSnr': snr,
            'hopLimit': 3 - hop_count,
            'hopStart': 3,
            'channel': 0
        }

        await self.message_queue.put(packet)

    async def simulate_node_info(self, node_id: str, short_name: str, long_name: str = None,
                                 hw_model: str = "HELTEC_V3", role: str = "CLIENT"):
        """Simulate receiving node info from another node."""
        packet = {
            'fromId': node_id,
            'toId': '^all',
            'decoded': {
                'portnum': 'NODEINFO_APP',
                'user': {
                    'id': f"!{int(node_id):08x}" if node_id.isdigit() else node_id,
                    'longName': long_name or short_name,
                    'shortName': short_name,
                    'hwModel': hw_model,
                    'role': role
                }
            },
            'rxRssi': -50 - random.randint(0, 50),
            'rxSnr': 6.5 - random.random() * 10,
            'hopLimit': 2,
            'hopStart': 3
        }

        # Also update nodes database
        self.nodes[node_id] = {
            'user': packet['decoded']['user']
        }

        await self.message_queue.put(packet)

    async def simulate_telemetry(self, node_id: str, battery: int = 85, voltage: float = 3.9,
                                channel_util: float = 0.0, air_util: float = 0.0):
        """Simulate receiving telemetry from another node."""
        packet = {
            'fromId': node_id,
            'toId': '^all',
            'decoded': {
                'portnum': 'TELEMETRY_APP',
                'telemetry': {
                    'deviceMetrics': {
                        'batteryLevel': battery,
                        'voltage': voltage,
                        'channelUtilization': channel_util,
                        'airUtilTx': air_util
                    }
                }
            },
            'rxRssi': -60 - random.randint(0, 40),
            'rxSnr': 4.0 - random.random() * 8,
            'hopLimit': 2,
            'hopStart': 3
        }

        await self.message_queue.put(packet)

    async def simulate_position(self, node_id: str, lat: float, lon: float, alt: int = 0):
        """Simulate receiving position from another node."""
        packet = {
            'fromId': node_id,
            'toId': '^all',
            'decoded': {
                'portnum': 'POSITION_APP',
                'position': {
                    'latitudeI': int(lat * 1e7),
                    'longitudeI': int(lon * 1e7),
                    'altitude': alt
                }
            },
            'rxRssi': -70 - random.randint(0, 30),
            'rxSnr': 3.0 - random.random() * 6,
            'hopLimit': 1,
            'hopStart': 3
        }

        await self.message_queue.put(packet)

    async def process_queue(self):
        """Process queued packets and call callbacks."""
        while True:
            try:
                packet = await asyncio.wait_for(self.message_queue.get(), timeout=0.1)
                if self.on_receive_callback:
                    await self.on_receive_callback(packet)
            except asyncio.TimeoutError:
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"Error processing packet: {e}")
                await asyncio.sleep(0.01)


class MockMeshtasticConnector:
    """Mock version of MeshtasticConnector for testing."""

    def __init__(self, port: str = "test", on_data_callback: Optional[Callable] = None):
        self.port = port
        self.on_data_callback = on_data_callback
        self.interface = MockMeshtasticInterface()
        self.local_node_id = self.interface.local_node_id
        self.local_node_hex_id = self.interface.local_node_hex
        self.connected = False
        self.node_db = {}
        self._process_task = None

    async def connect(self) -> bool:
        """Simulate connection."""
        self.interface.connect()
        self.connected = True

        # Set up callback
        self.interface.on_receive_callback = self._handle_packet

        # Start processing queue
        self._process_task = asyncio.create_task(self.interface.process_queue())

        # Send initial connection event
        if self.on_data_callback:
            await self.on_data_callback({
                "type": "connection",
                "connected": True,
                "timestamp": datetime.now()
            })

        # Send local node info
        await self._send_local_node_info()

        return True

    async def disconnect(self):
        """Simulate disconnection."""
        self.interface.disconnect()
        self.connected = False

        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass

        if self.on_data_callback:
            await self.on_data_callback({
                "type": "connection",
                "connected": False,
                "timestamp": datetime.now()
            })

    async def _send_local_node_info(self):
        """Send local node info on connection."""
        if self.on_data_callback:
            await self.on_data_callback({
                "type": "node_info",
                "node": {
                    "id": self.local_node_hex_id,
                    "short_name": "My Node",
                    "long_name": "Test Local Node",
                    "hardware_model": "RAK4631",
                    "role": "CLIENT",
                    "is_local": True
                },
                "rssi": None,
                "snr": None,
                "hop_count": 0,
                "timestamp": datetime.now()
            })

    async def _handle_packet(self, packet: Dict):
        """Handle incoming packet and convert to backend format."""
        if not self.on_data_callback:
            return

        portnum = packet.get('decoded', {}).get('portnum', '')

        if portnum == 'TEXT_MESSAGE_APP':
            await self._handle_text_message(packet)
        elif portnum == 'NODEINFO_APP':
            await self._handle_node_info(packet)
        elif portnum == 'TELEMETRY_APP':
            await self._handle_telemetry(packet)
        elif portnum == 'POSITION_APP':
            await self._handle_position(packet)

    async def _handle_text_message(self, packet: Dict):
        """Handle text message packet."""
        from_id = self.normalize_id(str(packet.get('fromId', '')))
        to_id = str(packet.get('toId', ''))

        if to_id == '^all' or to_id == '4294967295':
            to_id = 'broadcast'
        else:
            to_id = self.normalize_id(to_id)

        await self.on_data_callback({
            "type": "text_message",
            "from_id": from_id,
            "from_name": self.node_db.get(from_id, {}).get('short_name', f"Node {from_id[:8]}"),
            "to_id": to_id,
            "to_name": "All" if to_id == "broadcast" else self.node_db.get(to_id, {}).get('short_name', f"Node {to_id[:8]}"),
            "message": packet.get('decoded', {}).get('text', ''),
            "timestamp": datetime.now(),
            "rssi": packet.get('rxRssi'),
            "snr": packet.get('rxSnr'),
            "hop_count": packet.get('hopStart', 0) - packet.get('hopLimit', 0) if packet.get('hopStart', 0) > 0 else None
        })

    async def _handle_node_info(self, packet: Dict):
        """Handle node info packet."""
        user = packet.get('decoded', {}).get('user', {})
        node_id = self.normalize_id(user.get('id', str(packet.get('fromId', ''))))

        # Update node database
        self.node_db[node_id] = {
            'short_name': user.get('shortName', ''),
            'long_name': user.get('longName', ''),
            'hardware_model': user.get('hwModel', 'UNKNOWN'),
            'role': user.get('role', 'CLIENT')
        }

        await self.on_data_callback({
            "type": "node_info",
            "node": {
                "id": node_id,
                "short_name": user.get('shortName', ''),
                "long_name": user.get('longName', ''),
                "hardware_model": user.get('hwModel', 'UNKNOWN'),
                "role": user.get('role', 'CLIENT'),
                "is_local": node_id == self.local_node_hex_id
            },
            "rssi": packet.get('rxRssi'),
            "snr": packet.get('rxSnr'),
            "hop_count": packet.get('hopStart', 0) - packet.get('hopLimit', 0) if packet.get('hopStart', 0) > 0 else None,
            "timestamp": datetime.now()
        })

    async def _handle_telemetry(self, packet: Dict):
        """Handle telemetry packet."""
        node_id = self.normalize_id(str(packet.get('fromId', '')))
        device_metrics = packet.get('decoded', {}).get('telemetry', {}).get('deviceMetrics', {})

        await self.on_data_callback({
            "type": "telemetry",
            "node_id": node_id,
            "device_metrics": device_metrics,
            "timestamp": datetime.now(),
            "rssi": packet.get('rxRssi'),
            "snr": packet.get('rxSnr')
        })

    async def _handle_position(self, packet: Dict):
        """Handle position packet."""
        node_id = self.normalize_id(str(packet.get('fromId', '')))
        position = packet.get('decoded', {}).get('position', {})

        lat = position.get('latitudeI', 0) / 1e7 if position.get('latitudeI') else None
        lon = position.get('longitudeI', 0) / 1e7 if position.get('longitudeI') else None

        await self.on_data_callback({
            "type": "position_update",
            "node_id": node_id,
            "latitude": lat,
            "longitude": lon,
            "altitude": position.get('altitude'),
            "timestamp": datetime.now(),
            "rssi": packet.get('rxRssi'),
            "snr": packet.get('rxSnr')
        })

    def normalize_id(self, node_id: str) -> str:
        """Normalize node ID to hex format."""
        if not node_id:
            return node_id

        if node_id.startswith('!'):
            hex_part = node_id[1:]
            try:
                decimal_val = int(hex_part, 16)
                return f"!{decimal_val:08x}"
            except (ValueError, TypeError):
                return node_id

        try:
            decimal_id = int(node_id)
            return f"!{decimal_id:08x}"
        except (ValueError, TypeError):
            return node_id

    def send_text(self, text: str, destination_id: str = "^all", channel_index: int = 0) -> bool:
        """Send a text message."""
        return self.interface.sendText(text, destination_id, channel_index)

    def send_position(self, latitude: float, longitude: float, altitude: int = 0) -> bool:
        """Send position update."""
        return self.interface.sendPosition(latitude, longitude, altitude)

    async def simulate_incoming_message(self, from_id: str, to_id: str, text: str, **kwargs):
        """Simulate receiving a message."""
        await self.interface.simulate_incoming_message(from_id, to_id, text, **kwargs)

    async def simulate_node_info(self, node_id: str, short_name: str, **kwargs):
        """Simulate receiving node info."""
        await self.interface.simulate_node_info(node_id, short_name, **kwargs)

    async def simulate_telemetry(self, node_id: str, **kwargs):
        """Simulate receiving telemetry."""
        await self.interface.simulate_telemetry(node_id, **kwargs)

    async def simulate_position(self, node_id: str, lat: float, lon: float, **kwargs):
        """Simulate receiving position."""
        await self.interface.simulate_position(node_id, lat, lon, **kwargs)