# Release Notes

Date: 2025-09-15 (Updated)

This release focuses on safety (no unsolicited transmissions), reliability (fix message duplication and ordering), and UX improvements (private channel, messages modal, and groundwork for network visualization).

Highlights
- Safety first: The backend never transmits unless you explicitly send, or as a rate‑limited reply to a direct DM. No on‑connect announcements.
- Private channel: Set a private test channel index (0–7), see encryption status, and optionally send on that channel from Messenger and Node Details.
- Messages moved to modal: The Messages panel opens from the header, freeing right‑top space for network visualization.
- Direct‑only signal: RSSI/SNR and signal gauge show only for direct neighbors (hop_count = 0).
- DM Bot commands: PING, INFO, HELP, WEATHER, UPTIME, NODES, NEIGHBORS — per‑sender cooldowns + global budget. Replies use the same channel as the incoming DM.
- Dupes fixed at the root: No synthetic node_info on position; hop/signal updates use node_update. Connector handles enum/numeric ports. Initial/live message overlap filtered.
- Startup hygiene: start.sh pre‑kills old backend/frontend processes before starting fresh.

Technical changes
- Backend
  - WebSocket: unwraps `{type, data}` payloads correctly.
  - DM commands: implemented with per‑sender cooldowns and global rate cap; only for DMs to local node.
  - Test channel: `GET /api/device/status` returns `test_channel_index`; `POST /api/channel/test` sets/clears; `GET /api/device/channels` exposes safe channel info.
  - No unsolicited sends on connect.
  - node_update broadcast for hop/signal refresh; removed synthetic node_info from position_update.
  - Short‑window dedupe in broadcast path.
  - Connector: robust port classification (numeric and enum strings).
- Frontend
  - ActiveNodes/NodeDetails: hide RSSI/SNR and gauge unless direct (hop_count = 0).
  - Messages: moved into a modal; header badges show private channel + auto‑reply status.
  - Messenger: reply targeting; private channel toggle; pending “Sending…” clears on local echo with TTL fallback.
  - MessagesPanel: content+timestamp dedupe; explicit timestamp sorting.
  - App: seen message keys across initial/live to prevent duplicates.
  - Header controls: set/clear private channel index; toggle auto replies.

Known limitations
- Weather replies depend on available telemetry; not all nodes report environment metrics.
- Success_rate on network links is placeholder; path analytics to improve in upcoming iterations.

## Latest Updates (2025-09-15 Evening)

### Network Visualization Enhancements
- **Multiple visualization modes**: Switch between Radial, Tree, Grid, and Table views
  - **Radial view**: Improved with hover tooltips, reduced label clutter, better node spacing
  - **Tree view**: Hierarchical display with collapsible branches, shows routing paths clearly
  - **Grid view**: Signal-strength based layout with visual bars for direct connections
  - **Table view**: Sortable columns for detailed data analysis, handles 100+ nodes
- **Signal filtering**: RSSI/SNR now only displayed for directly connected nodes (hop_count = 0)
- **Visual improvements**: Node type icons, color-coded by hop distance, smooth transitions

### Packet Details Modal Improvements
- **Fixed z-index layering**: Packet details now properly appear above Messages modal
- **Enhanced visualization**:
  - Color-coded packet types with icons
  - Visual RSSI signal strength bar
  - Organized sections (Routing, Signal Quality, Metadata, Decoded Content)
  - Collapsible raw data section
- **Better UX**: Cleaner layout, proper spacing, formatted timestamps

Next up
- Path analytics overlay (neighbors, hop distribution, link quality trends).
- Optional allowlist for DM command senders; advanced rate‑limits.
- Performance optimizations for very large networks (200+ nodes)

