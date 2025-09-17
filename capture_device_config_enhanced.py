#!/usr/bin/env python3
"""
Enhanced utility to capture complete device configuration for comparison
Works with Meshtastic Python API 2.7.x
"""

import meshtastic
import meshtastic.serial_interface
import json
import sys
import base64
from datetime import datetime
import time

def capture_device_config_enhanced(device_path=None):
    """Capture comprehensive device configuration including all channels and encryption"""
    config = {
        "timestamp": datetime.now().isoformat(),
        "device_info": {},
        "channels": [],
        "security": {},
        "local_node": {},
        "radio_config": {},
        "lora_config": {},
        "display_config": {},
        "network_config": {},
        "position_config": {},
        "power_config": {},
        "bluetooth_config": {},
        "device_config": {}
    }

    try:
        # Connect to device
        print("Connecting to Meshtastic device...")
        if device_path:
            print(f"Using device path: {device_path}")
            interface = meshtastic.serial_interface.SerialInterface(devPath=device_path)
        else:
            print("Auto-detecting device...")
            interface = meshtastic.serial_interface.SerialInterface()

        # Give device time to send all data
        print("Waiting for device data...")
        time.sleep(2)

        # Get device metadata
        print("\n=== DEVICE METADATA ===")
        if hasattr(interface, 'metadata'):
            config["device_info"]["firmware_version"] = getattr(interface.metadata, 'firmware_version', 'Unknown')
            config["device_info"]["device_state_version"] = getattr(interface.metadata, 'device_state_version', 0)
            print(f"Firmware: {config['device_info']['firmware_version']}")

        # Get local node info
        print("\n=== LOCAL NODE INFO ===")
        if hasattr(interface, 'myInfo'):
            my_info = interface.myInfo
            config["local_node"]["node_num"] = getattr(my_info, 'my_node_num', None)
            config["local_node"]["node_hex"] = f"!{int(config['local_node']['node_num']):08x}" if config["local_node"]["node_num"] else None

            # Try to get more info from different attributes
            for attr in ['firmware_version', 'region', 'hw_model', 'hw_model_deprecated', 'message_timeout_msec', 'min_app_version']:
                if hasattr(my_info, attr):
                    config["local_node"][attr] = getattr(my_info, attr)

            config["local_node"]["has_private_key"] = hasattr(my_info, 'private_key') and my_info.private_key is not None
            config["local_node"]["has_public_key"] = hasattr(my_info, 'public_key') and my_info.public_key is not None

            print(f"Node Number: {config['local_node']['node_num']} ({config['local_node']['node_hex']})")
            print(f"Hardware Model: {config['local_node'].get('hw_model', 'Unknown')}")
            print(f"Region: {config['local_node'].get('region', 'Unknown')}")

            # Get PKC keys if available
            if hasattr(my_info, 'public_key') and my_info.public_key:
                pub_key = my_info.public_key
                config["security"]["public_key"] = base64.b64encode(pub_key).decode('utf-8')
                config["security"]["public_key_hex"] = pub_key.hex()
                print(f"PKC Public Key: {config['security']['public_key_hex'][:32]}...")

        # Get user info from nodeDB
        if hasattr(interface, 'nodes') and interface.nodes:
            local_node_num = config["local_node"].get("node_num")
            if local_node_num and local_node_num in interface.nodes:
                node = interface.nodes[local_node_num]
                if hasattr(node, 'user'):
                    user = node.user
                    config["local_node"]["short_name"] = getattr(user, 'short_name', None)
                    config["local_node"]["long_name"] = getattr(user, 'long_name', None)
                    config["local_node"]["is_licensed"] = getattr(user, 'is_licensed', False)
                    config["local_node"]["role"] = getattr(user, 'role', None)
                    print(f"Long Name: {config['local_node']['long_name']}")
                    print(f"Short Name: {config['local_node']['short_name']}")
                    print(f"Licensed: {config['local_node']['is_licensed']}")

        # Get complete channel configuration
        print("\n=== CHANNEL CONFIGURATION ===")
        if hasattr(interface, 'channels'):
            channels = interface.channels
            if channels:
                for idx, ch in channels.items() if isinstance(channels, dict) else enumerate(channels):
                    ch_info = {
                        "index": idx,
                        "role": None,
                        "name": None,
                        "id": None,
                        "psk": None,
                        "psk_base64": None,
                        "psk_hex": None,
                        "psk_type": None,
                        "psk_size": 0,
                        "uplink_enabled": False,
                        "downlink_enabled": False,
                        "module_settings": {}
                    }

                    # Get channel role
                    if hasattr(ch, 'role'):
                        ch_info["role"] = str(ch.role)

                    # Get channel settings
                    if hasattr(ch, 'settings'):
                        settings = ch.settings
                        ch_info["name"] = getattr(settings, 'name', None)
                        ch_info["id"] = getattr(settings, 'id', None)
                        ch_info["uplink_enabled"] = getattr(settings, 'uplink_enabled', False)
                        ch_info["downlink_enabled"] = getattr(settings, 'downlink_enabled', False)

                        # Get complete PSK information
                        psk = getattr(settings, 'psk', None)
                        if psk:
                            ch_info["psk_size"] = len(psk)
                            # Store actual PSK for backup purposes (be careful with this!)
                            if len(psk) > 0:
                                ch_info["psk_base64"] = base64.b64encode(psk).decode('utf-8')
                                ch_info["psk_hex"] = psk.hex()

                            # Determine PSK type
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

                        # Get module settings if present
                        if hasattr(settings, 'module_settings'):
                            mod_settings = settings.module_settings
                            if hasattr(mod_settings, 'position_precision'):
                                ch_info["module_settings"]["position_precision"] = mod_settings.position_precision

                    config["channels"].append(ch_info)
                    print(f"  Channel {idx}:")
                    print(f"    Name: {ch_info['name']}")
                    print(f"    Role: {ch_info['role']}")
                    print(f"    PSK Type: {ch_info['psk_type']}")
                    print(f"    PSK Size: {ch_info['psk_size']} bytes")
                    if ch_info['psk_hex']:
                        print(f"    PSK (hex): {ch_info['psk_hex'][:32]}..." if len(ch_info['psk_hex']) > 32 else f"    PSK (hex): {ch_info['psk_hex']}")
                    print(f"    Uplink: {ch_info['uplink_enabled']}, Downlink: {ch_info['downlink_enabled']}")

        # Get local configuration
        if hasattr(interface, 'localConfig'):
            local_config = interface.localConfig

            # Security configuration
            print("\n=== SECURITY CONFIGURATION ===")
            if hasattr(local_config, 'security'):
                security = local_config.security
                config["security"]["admin_channel_enabled"] = getattr(security, 'admin_channel_enabled', False)
                config["security"]["is_managed"] = getattr(security, 'is_managed', False)
                config["security"]["serial_enabled"] = getattr(security, 'serial_enabled', True)
                config["security"]["debug_log_api_enabled"] = getattr(security, 'debug_log_api_enabled', False)

                # Admin keys
                admin_key = getattr(security, 'admin_key', [])
                if admin_key:
                    config["security"]["admin_keys_count"] = len(admin_key)
                    config["security"]["admin_keys"] = [base64.b64encode(k).decode('utf-8') for k in admin_key if k]

                print(f"Admin Channel: {config['security']['admin_channel_enabled']}")
                print(f"Is Managed: {config['security']['is_managed']}")
                print(f"Serial Enabled: {config['security']['serial_enabled']}")
                print(f"Admin Keys: {config['security'].get('admin_keys_count', 0)}")

            # LoRa/Radio configuration
            print("\n=== LORA/RADIO CONFIGURATION ===")
            if hasattr(local_config, 'lora'):
                lora = local_config.lora
                config["lora_config"]["region"] = getattr(lora, 'region', None)
                config["lora_config"]["modem_preset"] = getattr(lora, 'modem_preset', None)
                config["lora_config"]["hop_limit"] = getattr(lora, 'hop_limit', None)
                config["lora_config"]["tx_power"] = getattr(lora, 'tx_power', None)
                config["lora_config"]["channel_num"] = getattr(lora, 'channel_num', None)
                config["lora_config"]["bandwidth"] = getattr(lora, 'bandwidth', None)
                config["lora_config"]["spread_factor"] = getattr(lora, 'spread_factor', None)
                config["lora_config"]["coding_rate"] = getattr(lora, 'coding_rate', None)
                config["lora_config"]["frequency_offset"] = getattr(lora, 'frequency_offset', None)
                config["lora_config"]["override_frequency"] = getattr(lora, 'override_frequency', None)
                config["lora_config"]["sx126x_rx_boosted_gain"] = getattr(lora, 'sx126x_rx_boosted_gain', None)
                config["lora_config"]["override_duty_cycle"] = getattr(lora, 'override_duty_cycle', None)
                config["lora_config"]["ignore_mqtt"] = getattr(lora, 'ignore_mqtt', None)

                print(f"Region: {config['lora_config']['region']}")
                print(f"Modem Preset: {config['lora_config']['modem_preset']}")
                print(f"TX Power: {config['lora_config']['tx_power']} dBm")
                print(f"Hop Limit: {config['lora_config']['hop_limit']}")
                print(f"Channel Num: {config['lora_config']['channel_num']}")

            # Device configuration
            print("\n=== DEVICE CONFIGURATION ===")
            if hasattr(local_config, 'device'):
                device = local_config.device
                config["device_config"]["role"] = getattr(device, 'role', None)
                config["device_config"]["rebroadcast_mode"] = getattr(device, 'rebroadcast_mode', None)
                config["device_config"]["node_info_broadcast_secs"] = getattr(device, 'node_info_broadcast_secs', None)
                config["device_config"]["button_gpio"] = getattr(device, 'button_gpio', None)
                config["device_config"]["buzzer_gpio"] = getattr(device, 'buzzer_gpio', None)
                config["device_config"]["double_tap_as_button_press"] = getattr(device, 'double_tap_as_button_press', None)
                config["device_config"]["tzdef"] = getattr(device, 'tzdef', None)

                print(f"Role: {config['device_config']['role']}")
                print(f"Rebroadcast Mode: {config['device_config']['rebroadcast_mode']}")
                print(f"Node Info Broadcast: {config['device_config']['node_info_broadcast_secs']} secs")

            # Network configuration
            if hasattr(local_config, 'network'):
                network = local_config.network
                config["network_config"]["wifi_enabled"] = getattr(network, 'wifi_enabled', False)
                config["network_config"]["wifi_ssid"] = getattr(network, 'wifi_ssid', None)
                config["network_config"]["wifi_psk"] = getattr(network, 'wifi_psk', None)
                config["network_config"]["ntp_server"] = getattr(network, 'ntp_server', None)
                config["network_config"]["eth_enabled"] = getattr(network, 'eth_enabled', False)

                if config["network_config"]["wifi_enabled"]:
                    print(f"\n=== NETWORK CONFIGURATION ===")
                    print(f"WiFi Enabled: {config['network_config']['wifi_enabled']}")
                    print(f"WiFi SSID: {config['network_config']['wifi_ssid']}")

            # Position configuration
            if hasattr(local_config, 'position'):
                position = local_config.position
                config["position_config"]["gps_mode"] = getattr(position, 'gps_mode', None)
                config["position_config"]["gps_update_interval"] = getattr(position, 'gps_update_interval', None)
                config["position_config"]["fixed_position"] = getattr(position, 'fixed_position', False)
                config["position_config"]["position_broadcast_secs"] = getattr(position, 'position_broadcast_secs', None)
                config["position_config"]["position_broadcast_smart_enabled"] = getattr(position, 'position_broadcast_smart_enabled', None)

            # Power configuration
            if hasattr(local_config, 'power'):
                power = local_config.power
                config["power_config"]["is_power_saving"] = getattr(power, 'is_power_saving', False)
                config["power_config"]["on_battery_shutdown_after_secs"] = getattr(power, 'on_battery_shutdown_after_secs', None)
                config["power_config"]["wait_bluetooth_secs"] = getattr(power, 'wait_bluetooth_secs', None)
                config["power_config"]["ls_secs"] = getattr(power, 'ls_secs', None)

            # Bluetooth configuration
            if hasattr(local_config, 'bluetooth'):
                bluetooth = local_config.bluetooth
                config["bluetooth_config"]["enabled"] = getattr(bluetooth, 'enabled', True)
                config["bluetooth_config"]["mode"] = getattr(bluetooth, 'mode', None)
                config["bluetooth_config"]["fixed_pin"] = getattr(bluetooth, 'fixed_pin', None)

            # Display configuration
            if hasattr(local_config, 'display'):
                display = local_config.display
                config["display_config"]["screen_on_secs"] = getattr(display, 'screen_on_secs', None)
                config["display_config"]["flip_screen"] = getattr(display, 'flip_screen', None)

        # Get module configurations
        print("\n=== MODULE CONFIGURATIONS ===")
        if hasattr(interface, 'moduleConfig'):
            module_config = interface.moduleConfig

            # MQTT module
            if hasattr(module_config, 'mqtt'):
                mqtt = module_config.mqtt
                config["mqtt_config"] = {
                    "enabled": getattr(mqtt, 'enabled', False),
                    "address": getattr(mqtt, 'address', None),
                    "username": getattr(mqtt, 'username', None),
                    "encryption_enabled": getattr(mqtt, 'encryption_enabled', False),
                    "json_enabled": getattr(mqtt, 'json_enabled', False),
                    "tls_enabled": getattr(mqtt, 'tls_enabled', False)
                }
                if config["mqtt_config"]["enabled"]:
                    print(f"MQTT: Enabled, Server: {config['mqtt_config']['address']}")

            # Telemetry module
            if hasattr(module_config, 'telemetry'):
                telemetry = module_config.telemetry
                config["telemetry_config"] = {
                    "device_update_interval": getattr(telemetry, 'device_update_interval', None),
                    "environment_update_interval": getattr(telemetry, 'environment_update_interval', None),
                    "environment_measurement_enabled": getattr(telemetry, 'environment_measurement_enabled', False),
                    "environment_screen_enabled": getattr(telemetry, 'environment_screen_enabled', False)
                }

        interface.close()
        return config

    except Exception as e:
        print(f"Error capturing config: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_config(config, device_name):
    """Save configuration to JSON file"""
    filename = f"{device_name}_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"\nConfiguration saved to: {filename}")
    return filename

def compare_configs(config1_file, config2_file):
    """Compare two device configurations"""
    with open(config1_file, 'r') as f:
        config1 = json.load(f)
    with open(config2_file, 'r') as f:
        config2 = json.load(f)

    print("\n" + "="*50)
    print("CONFIGURATION COMPARISON")
    print("="*50)

    # Compare firmware
    print("\n=== FIRMWARE ===")
    print(f"Device 1: {config1['device_info'].get('firmware_version', 'Unknown')}")
    print(f"Device 2: {config2['device_info'].get('firmware_version', 'Unknown')}")

    # Compare hardware
    print("\n=== HARDWARE ===")
    print(f"Device 1: {config1['local_node'].get('hw_model', 'Unknown')}")
    print(f"Device 2: {config2['local_node'].get('hw_model', 'Unknown')}")

    # Compare channels
    print("\n=== CHANNELS ===")
    print(f"Device 1: {len(config1.get('channels', []))} channels")
    print(f"Device 2: {len(config2.get('channels', []))} channels")

    # Compare encryption on primary channel
    if config1.get('channels') and config2.get('channels'):
        ch1 = next((ch for ch in config1['channels'] if ch['index'] == 0), None)
        ch2 = next((ch for ch in config2['channels'] if ch['index'] == 0), None)

        if ch1 and ch2:
            print(f"\nPrimary Channel Encryption:")
            print(f"Device 1: {ch1.get('psk_type', 'none')} ({ch1.get('psk_size', 0)} bytes)")
            print(f"Device 2: {ch2.get('psk_type', 'none')} ({ch2.get('psk_size', 0)} bytes)")

            if ch1.get('psk_hex') and ch2.get('psk_hex'):
                if ch1['psk_hex'] == ch2['psk_hex']:
                    print("✓ Encryption keys match")
                else:
                    print("✗ Encryption keys differ")

    # Compare LoRa settings
    print("\n=== LORA SETTINGS ===")
    lora1 = config1.get('lora_config', {})
    lora2 = config2.get('lora_config', {})

    settings = ['region', 'modem_preset', 'tx_power', 'hop_limit']
    for setting in settings:
        val1 = lora1.get(setting, 'Not set')
        val2 = lora2.get(setting, 'Not set')
        match = "✓" if val1 == val2 else "✗"
        print(f"{setting:20} Device 1: {val1:15} Device 2: {val2:15} {match}")

    # Compare security
    print("\n=== SECURITY ===")
    sec1 = config1.get('security', {})
    sec2 = config2.get('security', {})

    print(f"PKC Enabled:         Device 1: {sec1.get('public_key', None) is not None}  Device 2: {sec2.get('public_key', None) is not None}")
    print(f"Admin Channel:       Device 1: {sec1.get('admin_channel_enabled', False)}  Device 2: {sec2.get('admin_channel_enabled', False)}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Capture and compare Meshtastic device configurations')
    parser.add_argument('--device', '-d', help='Device path (e.g., /dev/ttyUSB0)')
    parser.add_argument('--name', '-n', default='device', help='Device name for output file')
    parser.add_argument('--compare', '-c', nargs=2, metavar=('config1.json', 'config2.json'),
                       help='Compare two configuration files')

    args = parser.parse_args()

    if args.compare:
        compare_configs(args.compare[0], args.compare[1])
    else:
        print(f"Capturing configuration for: {args.name}")
        config = capture_device_config_enhanced(args.device)

        if config:
            filename = save_config(config, args.name)

            # Print summary
            print("\n" + "="*50)
            print("DEVICE SUMMARY")
            print("="*50)
            print(f"Firmware: {config['device_info'].get('firmware_version', 'Unknown')}")
            print(f"Hardware: {config['local_node'].get('hw_model', 'Unknown')}")
            print(f"Node: {config['local_node'].get('long_name', 'Unknown')} ({config['local_node'].get('short_name', 'Unknown')})")
            print(f"Node ID: {config['local_node'].get('node_hex', 'Unknown')}")
            print(f"Channels: {len(config['channels'])}")
            print(f"Region: {config['lora_config'].get('region', 'Unknown')}")
            print(f"Has PKC Public Key: {config['security'].get('public_key', None) is not None}")
            print(f"Admin Channel Enabled: {config['security'].get('admin_channel_enabled', False)}")

            # Show channel details
            if config['channels']:
                print("\nChannels:")
                for ch in config['channels']:
                    print(f"  [{ch['index']}] {ch.get('name', 'Unnamed')} - {ch.get('psk_type', 'none')}")