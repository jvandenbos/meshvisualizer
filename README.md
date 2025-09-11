# Meshtastic Network Visualizer

A real-time network visualizer for Meshtastic mesh networks featuring a streamlined two-panel interface (nodes + messages), session management, and live updates with <100ms response times.

![Meshtastic Visualizer](https://img.shields.io/badge/Meshtastic-Visualizer-cyan)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![React](https://img.shields.io/badge/React-18-blue)
![TypeScript](https://img.shields.io/badge/TypeScript-5-blue)

## Features

### 🎯 Core Features
- **Two-Panel UI**: Nodes on the left, live messages on the right
- **Real-time Updates**: <100ms response time for all network events
- **Session Management**: View only current session data, with everything archived to SQLite
- **Bottom Ticker**: Scrolling activity ticker for quick awareness

### 📊 Visualization
- **Color-coded Signal Strength** (RSSI/SNR + gauge)
- **Battery Status** and voltage
- **Hop awareness**: LOCAL/DIRECT/⟨N⟩ HOPS with unknown handling
- **Active Nodes panel**: Beautiful, human-readable node list with detail modal
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
- **Filter messages** by type (Messages, Telemetry, Position, NodeInfo)
- **Inspect packets** via popup with human-readable decode and raw JSON
- **Event ticker** shows real-time activity

## Architecture

### Technology Stack
- **Backend**: FastAPI + WebSocket + Python Meshtastic API
- **Frontend**: React + TypeScript + Tailwind CSS
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
│       ├── components/  # UI components (ActiveNodes, MessagesPanel, modals)
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
- For networks >50 nodes, ensure hardware acceleration is enabled in browser
- The WebGPU renderer will automatically activate for large networks
- Check browser console for performance warnings

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
