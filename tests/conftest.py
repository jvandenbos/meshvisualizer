"""
Pytest configuration and shared fixtures for test suite.
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, List, Any
import sys
import os

# Add parent directory to path so we can import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import NodeInfo, TextMessage, Session
from backend.database import Database


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db():
    """Create a test database instance."""
    db = Database(db_path=":memory:")  # Use in-memory database for tests
    await db.initialize()
    await db.start_session()
    yield db
    # Cleanup happens automatically when memory DB is closed


@pytest.fixture
def local_node_id():
    """Standard local node ID for testing."""
    return "1109198442"  # Decimal format


@pytest.fixture
def local_node_hex():
    """Standard local node hex ID for testing."""
    return "!421d066a"  # 8-digit hex format


@pytest.fixture
def sample_nodes():
    """Create sample node data for testing."""
    return {
        "!421d066a": NodeInfo(
            id="!421d066a",
            short_name="My Node",
            long_name="Test Local Node",
            hardware_model="RAK4631",
            is_local=True,
            battery_level=100,
            voltage=4.2,
            rssi=-50,
            snr=6.5,
            last_heard=datetime.now(),
            hop_count=0
        ),
        "!54e05d0c": NodeInfo(
            id="!54e05d0c",
            short_name="Node 1",
            long_name="Test Remote Node 1",
            hardware_model="HELTEC_V3",
            is_local=False,
            battery_level=85,
            voltage=3.9,
            rssi=-75,
            snr=2.5,
            last_heard=datetime.now(),
            hop_count=1
        ),
        "!6c73d9ac": NodeInfo(
            id="!6c73d9ac",
            short_name="Node 2",
            long_name="Test Remote Node 2",
            hardware_model="TBEAM",
            is_local=False,
            battery_level=60,
            voltage=3.7,
            rssi=-95,
            snr=-2.0,
            last_heard=datetime.now(),
            hop_count=2
        )
    }


@pytest.fixture
def sample_messages():
    """Create sample text messages for testing."""
    return [
        TextMessage(
            from_id="!54e05d0c",
            from_name="Node 1",
            to_id="!421d066a",
            to_name="My Node",
            message="Hello local node",
            timestamp=datetime.now(),
            channel_index=0,
            is_direct=True
        ),
        TextMessage(
            from_id="!421d066a",
            from_name="My Node",
            to_id="!54e05d0c",
            to_name="Node 1",
            message="Hello remote node",
            timestamp=datetime.now(),
            channel_index=0,
            is_direct=True
        ),
        TextMessage(
            from_id="!6c73d9ac",
            from_name="Node 2",
            to_id="broadcast",
            to_name="All",
            message="Broadcast message",
            timestamp=datetime.now(),
            channel_index=0,
            is_direct=False
        ),
        TextMessage(
            from_id="!54e05d0c",
            from_name="Node 1",
            to_id="!421d066a",
            to_name="My Node",
            message="!help",
            timestamp=datetime.now(),
            channel_index=0,
            is_direct=True
        ),
        TextMessage(
            from_id="!6c73d9ac",
            from_name="Node 2",
            to_id="!421d066a",
            to_name="My Node",
            message="!info",
            timestamp=datetime.now(),
            channel_index=0,
            is_direct=True
        )
    ]