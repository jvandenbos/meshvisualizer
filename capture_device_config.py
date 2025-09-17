#!/usr/bin/env python3
"""
Utility to capture complete device configuration for comparison
"""

import meshtastic
import meshtastic.serial_interface
import json
import sys
import base64
from datetime import datetime

def capture_device_config():
    """Capture comprehensive device configuration"""
    config = {
        "timestamp": datetime.now().isoformat(),
        "device_info": {},
        "channels": [],
        "security": {},
        "local_node": {},
        "radio_config": {}
    }

    try:
        # Connect to device
        print("Connecting to Meshtastic device...")
        interface = meshtastic.serial_interface.SerialInterface()

        # Get device metadata
        if hasattr(interface, 'metadata'):
            config["device_info"]["firmware_version"] = getattr(interface.metadata, 'firmware_version', 'Unknown')
            config["device_info"]["device_state_version"] = getattr(interface.metadata, 'device_state_version', 0)

        # Get local node info
        if hasattr(interface, 'myInfo'):
            my_info = interface.myInfo
            config["local_node"]["node_num"] = getattr(my_info, 'my_node_num', None)
            config["local_node"]["firmware_version"] = getattr(my_info, 'firmware_version', None)
            config["local_node"]["region"] = getattr(my_info, 'region', None)
            config["local_node"]["hw_model"] = getattr(my_info, 'hw_model_deprecated', None)
            config["local_node"]["has_private_key"] = hasattr(my_info, 'private_key')
            config["local_node"]["has_public_key"] = hasattr(my_info, 'public_key')

            # Get public key for PKC
            if hasattr(my_info, 'public_key'):
                pub_key = my_info.public_key
                if pub_key:
                    config["security"]["public_key"] = base64.b64encode(pub_key).decode('utf-8')
                    config["security"]["public_key_hex"] = pub_key.hex()
                    print(f"Public Key (base64): {config['security']['public_key']}")
                    print(f"Public Key (hex): {config['security']['public_key_hex']}")

        # Get local node from nodeDB
        if interface.nodes:
            local_node_num = getattr(interface.myInfo, 'my_node_num', None)
            if local_node_num and local_node_num in interface.nodes:
                node = interface.nodes[local_node_num]
                if hasattr(node, 'user'):
                    user = node.user
                    config["local_node"]["short_name"] = getattr(user, 'short_name', None)
                    config["local_node"]["long_name"] = getattr(user, 'long_name', None)
                    config["local_node"]["is_licensed"] = getattr(user, 'is_licensed', False)
                    config["local_node"]["role"] = getattr(user, 'role', None)

        # Get channel configuration
        print("\nChannel Configuration:")
        if hasattr(interface, 'channels'):
            channels = interface.channels
            if isinstance(channels, dict):
                for idx, ch in channels.items():
                    ch_info = {
                        "index": idx,
                        "role": None,
                        "name": None,
                        "has_psk": False,
                        "psk_size": 0,
                        "uplink_enabled": False,
                        "downlink_enabled": False
                    }

                    # Get channel role
                    if hasattr(ch, 'role'):
                        ch_info["role"] = str(ch.role)

                    # Get channel settings
                    if hasattr(ch, 'settings'):
                        settings = ch.settings
                        ch_info["name"] = getattr(settings, 'name', None)

                        # Check PSK
                        psk = getattr(settings, 'psk', None)
                        if psk:
                            ch_info["has_psk"] = True
                            ch_info["psk_size"] = len(psk) if psk else 0
                            # Don't store actual PSK for security, just metadata
                            if len(psk) == 1 and psk[0] == 1:
                                ch_info["psk_type"] = "default"
                            elif len(psk) == 0:
                                ch_info["psk_type"] = "none"
                            elif len(psk) == 16:
                                ch_info["psk_type"] = "AES128"
                            elif len(psk) == 32:
                                ch_info["psk_type"] = "AES256"
                            else:
                                ch_info["psk_type"] = f"custom_{len(psk)}_bytes"
                        else:
                            ch_info["psk_type"] = "none"

                        ch_info["uplink_enabled"] = getattr(settings, 'uplink_enabled', False)
                        ch_info["downlink_enabled"] = getattr(settings, 'downlink_enabled', False)

                    config["channels"].append(ch_info)
                    print(f"  Channel {idx}: name='{ch_info['name']}', role={ch_info['role']}, psk_type={ch_info.get('psk_type', 'none')}")

        # Get security configuration
        if hasattr(interface, 'localConfig'):
            local_config = interface.localConfig
            if hasattr(local_config, 'security'):
                security = local_config.security
                config["security"]["admin_channel_enabled"] = getattr(security, 'admin_channel_enabled', False)
                config["security"]["is_managed"] = getattr(security, 'is_managed', False)

                # Check for admin keys
                admin_key = getattr(security, 'admin_key', [])
                if admin_key:
                    config["security"]["admin_keys_count"] = len(admin_key)
                    config["security"]["admin_keys"] = [base64.b64encode(k).decode('utf-8') for k in admin_key if k]
                else:
                    config["security"]["admin_keys_count"] = 0

        # Get radio configuration
        if hasattr(interface, 'localConfig'):
            local_config = interface.localConfig
            if hasattr(local_config, 'lora'):
                lora = local_config.lora
                config["radio_config"]["region"] = getattr(lora, 'region', None)
                config["radio_config"]["modem_preset"] = getattr(lora, 'modem_preset', None)
                config["radio_config"]["hop_limit"] = getattr(lora, 'hop_limit', None)
                config["radio_config"]["tx_power"] = getattr(lora, 'tx_power', None)
                config["radio_config"]["channel_num"] = getattr(lora, 'channel_num', None)

        interface.close()
        return config

    except Exception as e:
        print(f"Error capturing config: {e}")
        return None

def save_config(config, device_name):
    """Save configuration to JSON file"""
    filename = f"{device_name}_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"\nConfiguration saved to: {filename}")
    return filename

if __name__ == "__main__":
    device_name = sys.argv[1] if len(sys.argv) > 1 else "device"

    print(f"Capturing configuration for: {device_name}")
    config = capture_device_config()

    if config:
        save_config(config, device_name)

        # Print summary
        print("\n=== DEVICE SUMMARY ===")
        print(f"Firmware: {config['device_info'].get('firmware_version', 'Unknown')}")
        print(f"Node: {config['local_node'].get('long_name', 'Unknown')} ({config['local_node'].get('short_name', 'Unknown')})")
        print(f"Channels: {len(config['channels'])}")
        print(f"Has PKC Public Key: {config['security'].get('public_key', None) is not None}")
        print(f"Admin Channel Enabled: {config['security'].get('admin_channel_enabled', False)}")