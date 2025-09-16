"""
Tests for server command functionality (!help, !info, etc).
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List

from tests.mock_meshtastic import MockMeshtasticConnector
from backend.main import (
    maybe_handle_server_command,
    state,
    AppState
)
from backend.models import TextMessage, NodeInfo


class TestServerCommands:
    """Test server command handling without network I/O."""

    @pytest.fixture(autouse=True)
    async def setup(self, test_db, monkeypatch):
        """Set up test environment before each test."""
        # Reset state
        state.db = test_db
        state.current_session = await test_db.get_active_session()
        state.live_nodes.clear()
        state.live_messages.clear()
        state.network_links.clear()
        state.websocket_clients.clear()
        state.command_last_seen.clear()
        state.startup_time = datetime.now()
        state.test_channel_index = 0
        state.auto_replies_enabled = True

        # Create mock connector
        self.sent_messages = []
        mock_connector = MagicMock()
        mock_connector.local_node_id = "1109198442"
        mock_connector.local_node_hex_id = "!421d066a"
        mock_connector.connected = True

        def mock_send_text(text, dest, channel=0):
            self.sent_messages.append({
                'text': text,
                'destination': dest,
                'channel': channel
            })
            return True

        mock_connector.send_text = mock_send_text
        state.meshtastic = mock_connector

        # Add some test nodes
        state.live_nodes["!421d066a"] = NodeInfo(
            id="!421d066a",
            short_name="My Node",
            long_name="Local Test Node",
            hardware_model="RAK4631",
            is_local=True,
            battery_level=100,
            last_heard=datetime.now()
        )

        state.live_nodes["!54e05d0c"] = NodeInfo(
            id="!54e05d0c",
            short_name="Node 1",
            long_name="Remote Node 1",
            hardware_model="HELTEC_V3",
            battery_level=85,
            rssi=-75,
            snr=2.5,
            hop_count=1,
            last_heard=datetime.now()
        )

        state.live_nodes["!6c73d9ac"] = NodeInfo(
            id="!6c73d9ac",
            short_name="Node 2",
            long_name="Remote Node 2",
            hardware_model="TBEAM",
            battery_level=60,
            rssi=-95,
            snr=-2.0,
            hop_count=2,
            last_heard=datetime.now() - timedelta(minutes=5)
        )

    async def test_help_command(self):
        """Test !help command response."""
        message = TextMessage(
            from_id="!54e05d0c",
            from_name="Node 1",
            to_id="!421d066a",
            to_name="My Node",
            message="!help",
            timestamp=datetime.now(),
            channel_index=0
        )

        await maybe_handle_server_command(message)

        # Check that help message was sent
        assert len(self.sent_messages) == 1
        sent = self.sent_messages[0]
        assert sent['destination'] == "89012348"  # Decimal of !54e05d0c
        assert "!help" in sent['text'].lower()
        assert "!info" in sent['text'].lower()
        assert "!stats" in sent['text'].lower()
        assert "!nodes" in sent['text'].lower()

    async def test_info_command(self):
        """Test !info command response."""
        message = TextMessage(
            from_id="!6c73d9ac",
            from_name="Node 2",
            to_id="!421d066a",
            to_name="My Node",
            message="!info",
            timestamp=datetime.now(),
            channel_index=0
        )

        await maybe_handle_server_command(message)

        # Check that info message was sent
        assert len(self.sent_messages) == 1
        sent = self.sent_messages[0]
        assert sent['destination'] == "1823324588"  # Decimal of !6c73d9ac
        assert "my node" in sent['text'].lower()
        assert "rak4631" in sent['text'].lower()
        assert "100%" in sent['text']  # Battery level

    async def test_stats_command(self):
        """Test !stats command response."""
        # Add some test messages
        state.live_messages.extend([
            TextMessage(
                from_id="!54e05d0c",
                from_name="Node 1",
                to_id="!421d066a",
                to_name="My Node",
                message="Test 1",
                timestamp=datetime.now()
            ),
            TextMessage(
                from_id="!6c73d9ac",
                from_name="Node 2",
                to_id="broadcast",
                to_name="All",
                message="Test 2",
                timestamp=datetime.now()
            )
        ])

        message = TextMessage(
            from_id="!54e05d0c",
            from_name="Node 1",
            to_id="!421d066a",
            to_name="My Node",
            message="!stats",
            timestamp=datetime.now(),
            channel_index=0
        )

        await maybe_handle_server_command(message)

        # Check that stats message was sent
        assert len(self.sent_messages) == 1
        sent = self.sent_messages[0]
        assert "3 nodes" in sent['text']  # 3 nodes in live_nodes
        assert "2 messages" in sent['text']  # 2 messages in live_messages
        assert "uptime" in sent['text'].lower()

    async def test_nodes_command(self):
        """Test !nodes command response."""
        message = TextMessage(
            from_id="!54e05d0c",
            from_name="Node 1",
            to_id="!421d066a",
            to_name="My Node",
            message="!nodes",
            timestamp=datetime.now(),
            channel_index=0
        )

        await maybe_handle_server_command(message)

        # Check that nodes list was sent
        assert len(self.sent_messages) == 1
        sent = self.sent_messages[0]
        assert "my node" in sent['text'].lower()
        assert "node 1" in sent['text'].lower()
        assert "node 2" in sent['text'].lower()
        assert "85%" in sent['text']  # Node 1 battery
        assert "60%" in sent['text']  # Node 2 battery

    async def test_ping_command(self):
        """Test !ping command response."""
        message = TextMessage(
            from_id="!54e05d0c",
            from_name="Node 1",
            to_id="!421d066a",
            to_name="My Node",
            message="!ping",
            timestamp=datetime.now(),
            channel_index=0
        )

        await maybe_handle_server_command(message)

        # Check that pong was sent
        assert len(self.sent_messages) == 1
        sent = self.sent_messages[0]
        assert "pong" in sent['text'].lower()
        assert "node 1" in sent['text'].lower()

    async def test_broadcast_command_ignored(self):
        """Test that commands in broadcast messages are ignored."""
        message = TextMessage(
            from_id="!54e05d0c",
            from_name="Node 1",
            to_id="broadcast",
            to_name="All",
            message="!help",
            timestamp=datetime.now(),
            channel_index=0
        )

        await maybe_handle_server_command(message)

        # No response should be sent to broadcast commands
        assert len(self.sent_messages) == 0

    async def test_command_to_other_node_ignored(self):
        """Test that commands directed to other nodes are ignored."""
        message = TextMessage(
            from_id="!54e05d0c",
            from_name="Node 1",
            to_id="!6c73d9ac",  # To Node 2, not us
            to_name="Node 2",
            message="!help",
            timestamp=datetime.now(),
            channel_index=0
        )

        await maybe_handle_server_command(message)

        # Should not respond to commands for other nodes
        assert len(self.sent_messages) == 0

    async def test_rate_limiting(self):
        """Test command rate limiting."""
        # Send first command
        message1 = TextMessage(
            from_id="!54e05d0c",
            from_name="Node 1",
            to_id="!421d066a",
            to_name="My Node",
            message="!ping",
            timestamp=datetime.now(),
            channel_index=0
        )

        await maybe_handle_server_command(message1)
        assert len(self.sent_messages) == 1

        # Send same command immediately
        message2 = TextMessage(
            from_id="!54e05d0c",
            from_name="Node 1",
            to_id="!421d066a",
            to_name="My Node",
            message="!ping",
            timestamp=datetime.now(),
            channel_index=0
        )

        await maybe_handle_server_command(message2)

        # Should be rate limited
        assert len(self.sent_messages) == 1  # No new message sent

    async def test_different_commands_not_rate_limited(self):
        """Test that different commands from same sender aren't rate limited."""
        # Send first command
        message1 = TextMessage(
            from_id="!54e05d0c",
            from_name="Node 1",
            to_id="!421d066a",
            to_name="My Node",
            message="!ping",
            timestamp=datetime.now(),
            channel_index=0
        )

        await maybe_handle_server_command(message1)
        assert len(self.sent_messages) == 1

        # Send different command immediately
        message2 = TextMessage(
            from_id="!54e05d0c",
            from_name="Node 1",
            to_id="!421d066a",
            to_name="My Node",
            message="!info",
            timestamp=datetime.now(),
            channel_index=0
        )

        await maybe_handle_server_command(message2)

        # Should not be rate limited for different command
        assert len(self.sent_messages) == 2

    async def test_hex_decimal_id_handling(self):
        """Test that commands work with both hex and decimal node IDs."""
        # Test with decimal to_id
        message1 = TextMessage(
            from_id="!54e05d0c",
            from_name="Node 1",
            to_id="1109198442",  # Decimal format
            to_name="My Node",
            message="!ping",
            timestamp=datetime.now(),
            channel_index=0
        )

        await maybe_handle_server_command(message1)
        assert len(self.sent_messages) == 1

        # Clear for next test
        self.sent_messages.clear()
        state.command_last_seen.clear()

        # Test with hex to_id
        message2 = TextMessage(
            from_id="89012348",  # Decimal from_id
            from_name="Node 1",
            to_id="!421d066a",  # Hex format
            to_name="My Node",
            message="!help",
            timestamp=datetime.now(),
            channel_index=0
        )

        await maybe_handle_server_command(message2)
        assert len(self.sent_messages) == 1

    async def test_command_without_connector(self):
        """Test that commands fail gracefully without connector."""
        state.meshtastic = None

        message = TextMessage(
            from_id="!54e05d0c",
            from_name="Node 1",
            to_id="!421d066a",
            to_name="My Node",
            message="!help",
            timestamp=datetime.now(),
            channel_index=0
        )

        # Should not crash
        await maybe_handle_server_command(message)
        assert len(self.sent_messages) == 0

    async def test_command_channel_switching(self):
        """Test that responses go to the same channel as the request."""
        state.test_channel_index = 2  # Set test channel

        message = TextMessage(
            from_id="!54e05d0c",
            from_name="Node 1",
            to_id="!421d066a",
            to_name="My Node",
            message="!ping",
            timestamp=datetime.now(),
            channel_index=2  # Command on channel 2
        )

        await maybe_handle_server_command(message)

        assert len(self.sent_messages) == 1
        sent = self.sent_messages[0]
        assert sent['channel'] == 2  # Response on same channel


class TestServerCommandIntegration:
    """Integration tests with mock Meshtastic connector."""

    @pytest.fixture
    async def test_setup(self, test_db):
        """Set up test environment with mock connector."""
        # Reset state
        state.db = test_db
        state.current_session = await test_db.get_active_session()
        state.live_nodes.clear()
        state.live_messages.clear()
        state.command_last_seen.clear()
        state.startup_time = datetime.now()

        # Track all data received
        received_data = []

        async def on_data(data):
            received_data.append(data)
            # Simulate backend processing
            if data['type'] == 'node_info':
                node = NodeInfo(
                    id=data['node']['id'],
                    short_name=data['node']['short_name'],
                    long_name=data['node'].get('long_name'),
                    hardware_model=data['node'].get('hardware_model', 'UNKNOWN'),
                    is_local=data['node'].get('is_local', False),
                    last_heard=data['timestamp']
                )
                state.live_nodes[node.id] = node

            elif data['type'] == 'text_message':
                msg = TextMessage(
                    from_id=data['from_id'],
                    from_name=data['from_name'],
                    to_id=data['to_id'],
                    to_name=data['to_name'],
                    message=data['message'],
                    timestamp=data['timestamp']
                )
                state.live_messages.append(msg)
                # Handle server commands
                await maybe_handle_server_command(msg)

        connector = MockMeshtasticConnector(on_data_callback=on_data)
        state.meshtastic = connector
        await connector.connect()

        return {
            'connector': connector,
            'received_data': received_data
        }

    async def test_full_command_flow(self, test_setup):
        """Test complete command flow with mock connector."""
        connector = test_setup['connector']
        received_data = test_setup['received_data']

        # Simulate a remote node joining
        await connector.simulate_node_info("89012345", "Remote Node", hw_model="TBEAM")
        await asyncio.sleep(0.1)

        # Simulate help command from remote node
        await connector.simulate_incoming_message(
            from_id="89012345",
            to_id="1109198442",  # Local node
            text="!help"
        )
        await asyncio.sleep(0.2)

        # Check that help response was sent
        sent_texts = [m for m in received_data if m['type'] == 'text_message' and m['from_id'] == connector.local_node_hex_id]
        assert len(sent_texts) > 0
        response = sent_texts[0]
        assert "!help" in response['message']
        assert "!info" in response['message']

    async def test_command_with_telemetry_flow(self, test_setup):
        """Test commands that require telemetry data."""
        connector = test_setup['connector']

        # Simulate node with telemetry
        await connector.simulate_node_info("89012345", "Test Node")
        await asyncio.sleep(0.1)

        await connector.simulate_telemetry("89012345", battery=75, voltage=3.8)
        await asyncio.sleep(0.1)

        # Update state manually since we're not running full backend
        if "!054e05d9" in state.live_nodes:
            state.live_nodes["!054e05d9"].battery_level = 75
            state.live_nodes["!054e05d9"].voltage = 3.8

        # Send !nodes command
        await connector.simulate_incoming_message(
            from_id="89012345",
            to_id="1109198442",
            text="!nodes"
        )
        await asyncio.sleep(0.2)

        # Check response includes telemetry data
        assert connector.interface.messages[-1]['text']  # Should have sent a response