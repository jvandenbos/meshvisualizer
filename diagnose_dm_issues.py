#!/usr/bin/env python3
"""
Diagnose Direct Message (DM) decryption issues in Meshtastic networks
"""

import subprocess
import json
import base64
import sys

def get_node_info():
    """Get current node information from device"""
    try:
        result = subprocess.run(['meshtastic', '--info'],
                              capture_output=True, text=True, timeout=30)
        return result.stdout
    except Exception as e:
        print(f"Error getting node info: {e}")
        return None

def parse_nodes(info_text):
    """Parse node information from meshtastic --info output"""
    nodes = {}

    # Find the nodes section
    if '"Nodes in mesh"' not in info_text and 'Nodes in mesh:' not in info_text:
        return nodes

    # Extract JSON portion
    start = info_text.find('{', info_text.find('Nodes in mesh:'))
    if start == -1:
        return nodes

    # Find the matching closing brace
    brace_count = 0
    end = start
    for i in range(start, len(info_text)):
        if info_text[i] == '{':
            brace_count += 1
        elif info_text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break

    try:
        nodes_json = info_text[start:end]
        nodes = json.loads(nodes_json)
    except Exception as e:
        print(f"Error parsing nodes JSON: {e}")

    return nodes

def diagnose_dm_issues():
    """Diagnose DM decryption issues"""
    print("="*60)
    print("MESHTASTIC DM DECRYPTION DIAGNOSTIC")
    print("="*60)

    # Get current node info
    print("\n1. Getting current node information...")
    info_text = get_node_info()
    if not info_text:
        print("   ✗ Failed to get node information")
        return

    # Parse nodes
    nodes = parse_nodes(info_text)
    if not nodes:
        print("   ✗ No nodes found in mesh")
        return

    print(f"   ✓ Found {len(nodes)} nodes in mesh")

    # Extract local node info
    local_node_id = None
    for line in info_text.split('\n'):
        if '"myNodeNum":' in line:
            try:
                num = int(line.split('"myNodeNum":')[1].split(',')[0].strip())
                local_node_id = f"!{num:08x}"
                print(f"\n2. Local node ID: {local_node_id}")
                break
            except:
                pass

    # Check PKC configuration
    print("\n3. Checking PKC (Public Key Cryptography) status:")

    issues_found = []

    for node_id, node_data in nodes.items():
        if 'user' in node_data:
            user = node_data['user']
            long_name = user.get('longName', 'Unknown')
            short_name = user.get('shortName', '?')
            public_key = user.get('publicKey', None)

            print(f"\n   Node: {node_id} ({short_name} - {long_name})")

            if public_key:
                print(f"   Public Key: {public_key[:20]}...")

                # Check if this is the local node
                if node_id == local_node_id:
                    print("   [LOCAL NODE - has private key]")
            else:
                print("   ⚠️  No public key stored")
                if node_id != local_node_id:
                    issues_found.append(f"Missing public key for {node_id} ({short_name})")

    # Check channel configuration
    print("\n4. Checking channel configuration:")

    # Get channel info
    channel_output = subprocess.run(['meshtastic', '--info'],
                                  capture_output=True, text=True).stdout

    if 'Channels:' in channel_output:
        channels_section = channel_output[channel_output.find('Channels:'):]
        channels_lines = channels_section.split('\n')[:10]

        for line in channels_lines:
            if 'Index' in line and 'psk=' in line:
                print(f"   {line.strip()}")
                if 'psk=default' in line:
                    print("      ⚠️  Using default encryption (minimal security)")

    # Diagnosis summary
    print("\n" + "="*60)
    print("DIAGNOSIS RESULTS")
    print("="*60)

    if issues_found:
        print("\n⚠️  ISSUES FOUND:")
        for issue in issues_found:
            print(f"   • {issue}")

        print("\n📋 RECOMMENDED FIXES:")
        print("   1. Reset the node database to force key exchange:")
        print("      meshtastic --reset-nodedb")
        print("\n   2. Wait 30 seconds for nodes to exchange keys")
        print("\n   3. Send a test message to verify decryption works")
    else:
        print("\n✓ No obvious PKC issues detected")
        print("\nIf DMs still can't be decoded, check:")
        print("   • All devices have the same channel configuration")
        print("   • Firmware versions are compatible (2.6.x or higher for PKC)")
        print("   • Try sending a message to trigger key exchange")

    # Check for version mismatches
    print("\n5. Checking firmware versions:")
    firmware_versions = {}

    for line in info_text.split('\n'):
        if '"firmwareVersion":' in line:
            try:
                version = line.split('"firmwareVersion":')[1].split('"')[1]
                if version not in firmware_versions:
                    firmware_versions[version] = []
                # Try to associate with node
                # This is approximate - would need better parsing
                firmware_versions[version].append("node")
            except:
                pass

    if len(firmware_versions) > 1:
        print("   ⚠️  Multiple firmware versions detected:")
        for version in firmware_versions:
            print(f"      • {version}")
        print("   Consider updating all devices to the same version")
    elif firmware_versions:
        version = list(firmware_versions.keys())[0]
        print(f"   ✓ All devices on version: {version}")

if __name__ == "__main__":
    diagnose_dm_issues()