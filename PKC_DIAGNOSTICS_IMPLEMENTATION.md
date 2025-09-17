# PKC Diagnostics Implementation

## Overview
Enhanced the Meshtastic visualizer to track and diagnose PKC (Public Key Cryptography) failures for encrypted Direct Messages (DMs).

## Problem Solved
When DM encryption fails, the system now provides detailed diagnostics showing:
- Whether the node's public key is known
- When the key was last updated
- How many times it has changed
- Failure history and patterns

## Components Added

### 1. PKC Key History Manager (`backend/pkc_key_history.py`)
- Tracks public key history for all nodes
- Records key updates, changes, and failures
- Persists data to `pkc_key_history.json`
- Provides diagnostics for debugging

### 2. Enhanced Error Messages
When PKC decryption fails, messages now display:
```
[Encrypted DM - PKC failed] key:a1b2c3d4e5f67890... | age:2.5hr | updates:3 | fails:5
```

### 3. API Endpoints
- `GET /api/pkc/status` - Overall PKC system status
- `GET /api/pkc/node/{node_id}` - Detailed history for specific node
- `GET /api/pkc/failures` - List of nodes with decryption failures

### 4. Frontend PKC Status Component (`frontend/src/components/PKCStatus.tsx`)
- Interactive PKC diagnostics display
- Click to expand detailed information
- Shows recommendations for fixing issues

## Current Status

The PKC history file shows 20 nodes with decryption failures:
- **Total failures tracked**: 79 across all nodes
- **Nodes with most failures**: !6dc5aab3 (24 failures), !46b1b779 (21 failures)
- **Key observation**: All nodes have `current_key: null` - no public keys on record

This confirms the root cause: nodes haven't shared their public keys, making DM decryption impossible.

## How to Request Public Keys

### Method 1: Request NodeInfo (Triggers Key Exchange)
```python
# Using meshtastic CLI
meshtastic --dest !node_id --request-node-info

# In Python
interface.sendNodeInfo(destinationId='!node_id', requestResponse=True)
```

### Method 2: Send Telemetry Request (Often Includes Keys)
```python
# Using meshtastic CLI
meshtastic --dest !node_id --request-telemetry

# In Python
interface.sendTelemetry(destinationId='!node_id')
```

### Method 3: Force Key Broadcast
```python
# Broadcast your own public key
interface.sendNodeInfo(includePublicKey=True)
```

### Method 4: Automatic Key Request on Failure
The PKC Key Manager (`backend/pkc_key_manager.py`) already implements automatic key refresh:
1. Detects DM decryption failure
2. Removes stale node from database
3. Requests fresh NodeInfo
4. Waits for key exchange

## Implementation Details

### Key Tracking Flow
1. **Node Discovery**: When a node is discovered, check for public key
2. **Key Storage**: Store key in PKC history with timestamp
3. **Failure Detection**: Track decryption failures per node
4. **Diagnostics**: Show key age, update count, failure patterns
5. **Auto-Recovery**: Request fresh keys after failures

### Data Structure
```json
{
  "!node_id": {
    "node_name": "NodeName",
    "current_key": "hex_key_string",
    "last_updated": "2025-09-17T12:00:00",
    "history": [
      {
        "key": "old_hex_key",
        "added": "2025-09-16T10:00:00",
        "removed": "2025-09-17T12:00:00",
        "duration_hours": 26.0
      }
    ],
    "update_count": 3,
    "decryption_failures": 5,
    "last_failure": "2025-09-17T13:00:00"
  }
}
```

## Usage

### View PKC Status
```bash
# Overall status
curl http://localhost:8000/api/pkc/status | jq .

# Specific node
curl http://localhost:8000/api/pkc/node/!46b1b779 | jq .

# All failures
curl http://localhost:8000/api/pkc/failures | jq .
```

### Monitor in UI
1. Watch the Event Ticker for PKC failure notifications
2. Check the Messages Panel for enhanced error messages
3. Click on PKC status badges for detailed diagnostics

## Next Steps

1. **Implement Proactive Key Collection**
   - Request keys from nodes on first contact
   - Periodic key refresh for stale keys (>24 hours old)
   - Batch key requests during network discovery

2. **Add Key Management UI**
   - Dashboard showing PKC health
   - Manual key request buttons
   - Visual indicators for nodes missing keys

3. **Enhance Recovery Logic**
   - Exponential backoff for failed requests
   - Smart retry based on network conditions
   - Key exchange verification

## Files Modified
- `backend/pkc_key_history.py` (new)
- `backend/meshtastic_connector.py` (enhanced)
- `backend/main.py` (added API endpoints)
- `frontend/src/components/PKCStatus.tsx` (new)
- `frontend/src/App.tsx` (integrated PKC status)