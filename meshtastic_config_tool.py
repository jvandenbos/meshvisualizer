#!/usr/bin/env python3
"""
Comprehensive Meshtastic Configuration Tool
Captures, compares, and exports device configurations
Works with Meshtastic Python API 2.7.x and CLI
"""

import subprocess
import json
import yaml
import sys
from datetime import datetime
from pathlib import Path
import argparse

def run_meshtastic_cli(args):
    """Run meshtastic CLI command and return output"""
    try:
        result = subprocess.run(
            ['meshtastic'] + args,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        print("CLI command timed out")
        return None
    except Exception as e:
        print(f"Error running CLI: {e}")
        return None

def capture_device_config(device_name="device", device_path=None):
    """Capture complete device configuration using CLI"""

    print(f"Capturing configuration for: {device_name}")
    print("="*50)

    # Build base command
    base_cmd = []
    if device_path:
        base_cmd.extend(['--port', device_path])

    # Create output directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(f"{device_name}_config_{timestamp}")
    output_dir.mkdir(exist_ok=True)

    config_summary = {
        "timestamp": datetime.now().isoformat(),
        "device_name": device_name,
        "files_created": []
    }

    # 1. Export full YAML configuration
    print("1. Exporting full configuration...")
    yaml_file = output_dir / "full_config.yaml"
    yaml_output = run_meshtastic_cli(base_cmd + ['--export-config'])
    if yaml_output:
        with open(yaml_file, 'w') as f:
            f.write(yaml_output)
        print(f"   ✓ Saved to {yaml_file}")
        config_summary["files_created"].append(str(yaml_file))

    # 2. Get device info
    print("2. Getting device info...")
    info_file = output_dir / "device_info.txt"
    info_output = run_meshtastic_cli(base_cmd + ['--info'])
    if info_output:
        with open(info_file, 'w') as f:
            f.write(info_output)
        print(f"   ✓ Saved to {info_file}")
        config_summary["files_created"].append(str(info_file))

        # Parse key information
        for line in info_output.split('\n'):
            if 'firmwareVersion' in line:
                config_summary['firmware'] = line.split('"firmwareVersion": "')[1].split('"')[0]
            if 'hwModel' in line and 'Metadata' in info_output[:info_output.index(line)]:
                config_summary['hardware'] = line.split('"hwModel": "')[1].split('"')[0]

    # 3. Get channel URLs
    print("3. Getting channel URLs...")
    url_file = output_dir / "channel_urls.txt"
    url_output = run_meshtastic_cli(base_cmd + ['--qr-all'])
    if url_output:
        with open(url_file, 'w') as f:
            f.write(url_output)
        print(f"   ✓ Saved to {url_file}")
        config_summary["files_created"].append(str(url_file))

    # 4. Get specific configurations
    configs_to_get = [
        'device', 'lora', 'bluetooth', 'network', 'position',
        'power', 'security', 'display', 'mqtt'
    ]

    print("4. Getting specific configurations...")
    for config in configs_to_get:
        config_file = output_dir / f"config_{config}.json"
        config_output = run_meshtastic_cli(base_cmd + ['--get', config])
        if config_output:
            try:
                # Extract JSON from output
                json_start = config_output.find('{')
                if json_start >= 0:
                    json_str = config_output[json_start:]
                    # Find the end of JSON
                    brace_count = 0
                    json_end = 0
                    for i, char in enumerate(json_str):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break

                    if json_end > 0:
                        json_str = json_str[:json_end]
                        config_data = json.loads(json_str)
                        with open(config_file, 'w') as f:
                            json.dump(config_data, f, indent=2)
                        print(f"   ✓ Got {config} config")

                        # Store key security info
                        if config == 'security' and 'publicKey' in config_data:
                            config_summary['has_pkc'] = True
                            config_summary['public_key'] = config_data['publicKey']
            except Exception as e:
                print(f"   ✗ Failed to parse {config}: {e}")

    # 5. Get module configurations
    modules_to_get = [
        'telemetry', 'range_test', 'audio', 'serial',
        'external_notification', 'canned_message'
    ]

    print("5. Getting module configurations...")
    for module in modules_to_get:
        module_output = run_meshtastic_cli(base_cmd + ['--get', module])
        if module_output and '{' in module_output:
            module_file = output_dir / f"module_{module}.json"
            try:
                json_start = module_output.find('{')
                json_str = module_output[json_start:]
                # Find matching closing brace
                brace_count = 0
                json_end = 0
                for i, char in enumerate(json_str):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break

                if json_end > 0:
                    json_str = json_str[:json_end]
                    module_data = json.loads(json_str)
                    with open(module_file, 'w') as f:
                        json.dump(module_data, f, indent=2)
                    print(f"   ✓ Got {module} module")
            except:
                pass

    # 6. Save summary
    summary_file = output_dir / "summary.json"
    with open(summary_file, 'w') as f:
        json.dump(config_summary, f, indent=2)

    print("\n" + "="*50)
    print("CAPTURE COMPLETE")
    print("="*50)
    print(f"Device: {device_name}")
    print(f"Firmware: {config_summary.get('firmware', 'Unknown')}")
    print(f"Hardware: {config_summary.get('hardware', 'Unknown')}")
    print(f"Has PKC: {config_summary.get('has_pkc', False)}")
    print(f"Files saved in: {output_dir}/")
    print("\nTo compare with another device later, run:")
    print(f"  python3 {sys.argv[0]} --compare {output_dir} <other_device_dir>")

    return output_dir

def compare_configs(dir1, dir2):
    """Compare two device configuration directories"""

    dir1 = Path(dir1)
    dir2 = Path(dir2)

    print("\n" + "="*50)
    print("CONFIGURATION COMPARISON")
    print("="*50)
    print(f"Device 1: {dir1.name}")
    print(f"Device 2: {dir2.name}")
    print("="*50)

    # Load YAML configs
    yaml1 = dir1 / "full_config.yaml"
    yaml2 = dir2 / "full_config.yaml"

    if yaml1.exists() and yaml2.exists():
        with open(yaml1) as f:
            config1 = yaml.safe_load(f)
        with open(yaml2) as f:
            config2 = yaml.safe_load(f)

        print("\n=== CHANNEL COMPARISON ===")
        url1 = config1.get('channel_url', '')
        url2 = config2.get('channel_url', '')

        if url1 == url2:
            print("✓ Channel URLs match - devices can communicate")
        else:
            print("✗ Channel URLs differ - devices cannot communicate")
            print(f"  Device 1: {url1[:50]}...")
            print(f"  Device 2: {url2[:50]}...")

        print("\n=== LORA SETTINGS ===")
        lora1 = config1.get('config', {}).get('lora', {})
        lora2 = config2.get('config', {}).get('lora', {})

        settings = ['region', 'hopLimit', 'txPower', 'channelNum', 'usePreset']
        for setting in settings:
            val1 = lora1.get(setting, 'Not set')
            val2 = lora2.get(setting, 'Not set')
            match = "✓" if val1 == val2 else "✗"
            print(f"{setting:20} Device 1: {str(val1):15} Device 2: {str(val2):15} {match}")

        print("\n=== SECURITY ===")
        sec1 = config1.get('config', {}).get('security', {})
        sec2 = config2.get('config', {}).get('security', {})

        print(f"Has Public Key:      Device 1: {'publicKey' in sec1}  Device 2: {'publicKey' in sec2}")
        print(f"Serial Enabled:      Device 1: {sec1.get('serialEnabled', True)}  Device 2: {sec2.get('serialEnabled', True)}")

        print("\n=== DEVICE SETTINGS ===")
        dev1 = config1.get('config', {}).get('device', {})
        dev2 = config2.get('config', {}).get('device', {})

        settings = ['role', 'nodeInfoBroadcastSecs', 'tzdef']
        for setting in settings:
            val1 = dev1.get(setting, 'Default')
            val2 = dev2.get(setting, 'Default')
            match = "✓" if val1 == val2 else "✗"
            print(f"{setting:25} Device 1: {str(val1)[:20]:20} Device 2: {str(val2)[:20]:20} {match}")

    # Compare summaries
    summary1 = dir1 / "summary.json"
    summary2 = dir2 / "summary.json"

    if summary1.exists() and summary2.exists():
        with open(summary1) as f:
            sum1 = json.load(f)
        with open(summary2) as f:
            sum2 = json.load(f)

        print("\n=== DEVICE INFO ===")
        print(f"Firmware:            Device 1: {sum1.get('firmware', 'Unknown')}  Device 2: {sum2.get('firmware', 'Unknown')}")
        print(f"Hardware:            Device 1: {sum1.get('hardware', 'Unknown')}  Device 2: {sum2.get('hardware', 'Unknown')}")

def main():
    parser = argparse.ArgumentParser(
        description='Meshtastic Configuration Tool - Capture and compare device configs'
    )
    parser.add_argument('--device', '-d', help='Device path (e.g., /dev/ttyUSB0)')
    parser.add_argument('--name', '-n', default='device',
                       help='Device name for output directory')
    parser.add_argument('--compare', '-c', nargs=2,
                       metavar=('config_dir1', 'config_dir2'),
                       help='Compare two configuration directories')

    args = parser.parse_args()

    if args.compare:
        compare_configs(args.compare[0], args.compare[1])
    else:
        # Capture current device
        capture_device_config(args.name, args.device)

if __name__ == "__main__":
    main()