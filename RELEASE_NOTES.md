# Release Notes

Date: 2025-09-15

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

Next up
- Network visualization (graph) in right‑top space with live links and basic analytics.
- Path analytics overlay (neighbors, hop distribution, link quality trends).
- Optional allowlist for DM command senders; advanced rate‑limits.

