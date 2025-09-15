# Meshtastic Network Visualizer

A real-time network visualizer for Meshtastic mesh networks featuring a streamlined two-panel interface (nodes + messages), a resizable packets/messenger split, an optional map with hop badges and clustering, session management, and live updates with <100ms response times.

![Meshtastic Visualizer](https://img.shields.io/badge/Meshtastic-Visualizer-cyan)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![React](https://img.shields.io/badge/React-18-blue)
![TypeScript](https://img.shields.io/badge/TypeScript-5-blue)

## Features

### 🎯 Core Features
- **Two-Panel UI**: Nodes on the left; right side split into Packets (top) and Messenger (bottom)
- **Resizable Right Split**: Drag the divider between Packets and Messenger
- **Real-time Updates**: <100ms response time for all network events
- **Session Management**: View only current session data, with everything archived to SQLite
- **Bottom Ticker**: Scrolling activity ticker for quick awareness

### 📊 Visualization
- **Hop Awareness**: LOCAL/DIRECT/N HOPS/UNKNOWN badges always visible
- **Signal**: RSSI/SNR + compact gauge; direct links show an estimated distance bar
- **Battery/Voltage**: Quick device health in the node list
- **Map Modal**: Markers for all nodes with coordinates, hop-count badges, simple clustering, and a mini legend
- **Event Ticker**: Scrolling feed of network events

### 📡 Device Support
- **RAK 4631** connected via USB-C (primary target)
- Auto-detection of Meshtastic devices
- Support for all Meshtastic hardware models

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- RAK 4631 or compatible Meshtastic device connected via USB-C

### Installation & Running

```bash
# Clone the repository
git clone <repository-url>
cd meshtastic-visualizer

# Run the start script
./start.sh
```

The start script will:
1. Install Python dependencies
2. Install frontend dependencies
3. Initialize the database
4. Start the backend server (port 8000)
5. Start the frontend dev server (port 5173)

### Manual Setup

If you prefer manual setup:

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..

# Start backend
uvicorn backend.main:app --reload --port 8000

# In another terminal, start frontend
cd frontend
npm run dev
```

## Usage

1. **Connect your RAK 4631** via USB-C
2. Open browser at **http://localhost:5173**
3. Click **"Connect"** to connect to your device
4. Watch as nodes appear and the network forms
5. Use **"New Session"** to clear the display and start fresh

### Controls
- **Click nodes** to open a detailed node modal (request telemetry/position)
- **Right pane**: Filter packets by type; click a row to Inspect (human-readable decode + raw JSON)
- **Messenger**: Type and press Enter or click Send; shows “Sending…” pending and ✓ Delivered when echoed
- **Map**: Use the Map button in the Packets header to open the map modal
- **Divider**: Drag the bar between Packets and Messenger to resize
- **Ticker**: Bottom bar shows activity

## Architecture

### Technology Stack
- **Backend**: FastAPI + WebSocket + Python Meshtastic API
- **Frontend**: React + TypeScript + Tailwind CSS + React‑Leaflet
- **Database**: SQLite with session-based architecture
- **Real-time**: WebSocket for <100ms updates

### Project Structure
```
meshtastic-visualizer/
├── backend/              # FastAPI server
│   ├── main.py          # Main application
│   ├── meshtastic_connector.py  # Device interface
│   ├── database.py      # SQLite operations
│   └── models.py        # Data models
├── frontend/            # React application
│   └── src/
│       ├── components/  # UI components (ActiveNodes, MessagesPanel, ChatPanel, MapModal)
│       ├── services/    # WebSocket service
│       └── App.tsx      # Main app
├── requirements.txt     # Python dependencies
├── start.sh            # Startup script
└── README.md           # This file
```

## Development

### Backend Development
The backend uses FastAPI with automatic reload:
```bash
uvicorn backend.main:app --reload --port 8000
```

API documentation available at: http://localhost:8000/docs

### Frontend Development
The frontend uses Vite for fast HMR:
```bash
cd frontend
npm run dev
```

### Database
SQLite database is created automatically at `meshtastic.db`. Schema includes:
- Sessions management
- Node information and history
- Message storage
- Network topology
- Telemetry data

## API Endpoints

### WebSocket
- `ws://localhost:8000/ws` - Real-time data stream

### REST API
- `GET /api/session/current` - Get current session
- `POST /api/session/new` - Start new session
- `GET /api/nodes` - Get active nodes
- `GET /api/messages` - Get recent messages
- `GET /api/topology` - Get network topology
- `POST /api/device/connect` - Connect to device
- `POST /api/device/disconnect` - Disconnect from device
- `GET /api/device/status` - Get connection status
- `POST /api/channel/test` - Set/clear private test channel index

## Meshtastic Server Commands (via DM)

The backend can respond to direct text messages sent to the local node. Commands are rate‑limited per sender to prevent abuse.

- PING: Replies with "Acknowledge, you are X hop(s) away." Uses the observed hop count on the received packet; falls back to unknown if not available. Cooldown: 5s.
- INFO: Replies with a concise summary like: "Nodes: N (Direct D, Multi M). Uptime: 1h 23m. MyID: 1109198442." Cooldown: 15s.
- HELP: Brief command list. Cooldown: 10s.
- WEATHER: Reports latest environmental telemetry (T/RH/Pressure) from the local node if available, else any node with env metrics (prefers direct neighbors). Cooldown: 30s.
- UPTIME: Returns the backend uptime. Cooldown: 10s.
- NODES: Returns counts (total, direct, multi-hop). Cooldown: 10s.
- NEIGHBORS: Direct neighbors count and up to 5 names. Cooldown: 10s.

Security/rate limiting:
- Per‑sender cooldowns as noted above.
- Broadcast messages are ignored; only direct messages to our node are considered.
- The backend does not execute user content; only known commands are handled.

## Private/Test Channel

To avoid sending to the public mesh, you can set a private channel index for testing. The device must already have that channel configured (e.g., created via the Meshtastic app with a unique PSK). The frontend Messenger can then opt-in to send via this channel.

- Set test channel index:
  - `POST /api/channel/test` with `{ "index": 2 }` (0–7). Use `null` to clear.
- Check status:
  - `GET /api/device/status` includes `test_channel_index` when set.
- Messenger UI: toggle “Private ch X” to send via that index.
- DM replies continue on the channel they were received on (responses only).

Note: This does not change radio channel configuration; it only selects the transmit channel index for messages we send. Ensure the node is subscribed to that channel to receive them.

## Troubleshooting

### Device Not Found
- Ensure RAK 4631 is connected via USB-C (data cable, not charge-only)
- On Linux: Add user to `dialout` group: `sudo usermod -a -G dialout $USER`
- On macOS: Check System Preferences > Security for USB permissions

### Connection Issues
- Check that no other application is using the serial port
- Try specifying device path manually in the Connect dialog
- Restart the Meshtastic device

### Performance
- For larger networks, ensure hardware acceleration is enabled in the browser
- Check the browser console for WebSocket logs and warnings

## Name Aliases (Human‑Readable Names)

You can provide friendly names for nodes in `frontend/public/aliases.json` (loaded automatically):

```json
{
  "066a": "jasper-sky",
  "1109198442": "My Base Station"
}
```

Matching is by exact ID, or a suffix/substring of the ID (e.g., "066a"). Display names resolve in this order: `long_name → alias → short_name → id`.

## Delivery and Pending Messages

The Messenger shows outgoing messages immediately as “Sending…”. When a `text_message` is received from your local node, it flips to “✓ Delivered”. If your device/connector does not echo locally‑sent messages, they will remain in the pending style; we can add a timeout‑based “Sent” state if needed.

## Release Notes

See RELEASE_NOTES.md for the latest changes and upgrade notes.

## Contributing

Contributions welcome! Please follow these guidelines:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with a real Meshtastic device
5. Submit a pull request

## License

MIT License - See LICENSE file for details

## Acknowledgments

- Meshtastic project for the amazing mesh networking platform
- FastAPI for the high-performance Python web framework

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Join the Meshtastic Discord community
- Check the [Meshtastic documentation](https://meshtastic.org)

---

Built with ❤️ for the Meshtastic community
