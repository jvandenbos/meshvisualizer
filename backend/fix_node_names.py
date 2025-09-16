#!/usr/bin/env python3
"""
Script to fix existing nodes with default "Node-" names
Gives them friendly generated names instead
"""

import asyncio
import aiosqlite
from name_generator import generate_friendly_name
from datetime import datetime

async def fix_node_names():
    """Update all nodes with Node- prefix to use friendly names"""

    async with aiosqlite.connect("../meshtastic.db") as db:
        # Get current session
        cursor = await db.execute("""
            SELECT id FROM sessions WHERE is_active = TRUE
        """)
        session = await cursor.fetchone()
        if not session:
            print("No active session found")
            return

        session_id = session[0]

        # Find all nodes with Node- prefix
        cursor = await db.execute("""
            SELECT id, short_name FROM nodes
            WHERE session_id = ? AND short_name LIKE 'Node-%'
        """, (session_id,))

        nodes_to_fix = await cursor.fetchall()

        if not nodes_to_fix:
            print("No nodes with 'Node-' prefix found")
            return

        print(f"Found {len(nodes_to_fix)} nodes to fix:")

        for node_id, old_name in nodes_to_fix:
            # Generate friendly name
            friendly_name = generate_friendly_name(node_id)

            # Update the node
            await db.execute("""
                UPDATE nodes
                SET short_name = ?
                WHERE id = ? AND session_id = ?
            """, (friendly_name, node_id, session_id))

            # Add to generated_names table
            now = int(datetime.now().timestamp())
            await db.execute("""
                INSERT OR REPLACE INTO generated_names
                (node_id, generated_name, created_at, last_used, is_active)
                VALUES (?, ?, ?, ?, TRUE)
            """, (node_id, friendly_name, now, now))

            print(f"  {old_name} → {friendly_name}")

        await db.commit()
        print(f"\n✅ Updated {len(nodes_to_fix)} nodes with friendly names")

if __name__ == "__main__":
    asyncio.run(fix_node_names())