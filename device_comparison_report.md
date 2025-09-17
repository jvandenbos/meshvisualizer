# Meshtastic Device Configuration Comparison Report

**Date**: 2025-09-17
**Devices Compared**: RAK4631 vs T-Deck Plus

## Executive Summary

Both devices are running the same firmware version but have different channel configurations, preventing them from communicating on secondary channels.

## Device Information

| Parameter | RAK4631 | T-Deck Plus | Match |
|-----------|---------|-------------|-------|
| **Firmware** | 2.6.11.60ec05e | 2.6.11.60ec05e | ✓ |
| **Hardware Model** | RAK4631 | T_DECK | ✗ |
| **Node ID** | !421d066a | !a0a53aa4 | ✗ |
| **Owner Name** | jsp-server-msgmeHELP | jsp-rover1 | ✗ |
| **Short Name** | jsp0 | jsp1 | ✗ |
| **PKC Support** | Yes | Yes | ✓ |

## Channel Configuration

### Primary Channel (Index 0)
| Parameter | RAK4631 | T-Deck Plus | Match |
|-----------|---------|-------------|-------|
| **PSK Type** | Default (AQ==) | Default (AQ==) | ✓ |
| **Name** | (empty) | (empty) | ✓ |
| **Position Precision** | 13 | 13 | ✓ |
| **Uplink Enabled** | false | false | ✓ |
| **Downlink Enabled** | false | false | ✓ |

### Secondary Channels
| Device | Channel Count | Details |
|--------|--------------|---------|
| **RAK4631** | 2 channels | Has secondary channel "jasper" with custom encryption |
| **T-Deck Plus** | 1 channel | No secondary channels configured |

**⚠️ ISSUE**: The T-Deck Plus is missing the secondary "jasper" channel that exists on the RAK4631.

## LoRa/Radio Configuration

| Parameter | RAK4631 | T-Deck Plus | Match | Impact |
|-----------|---------|-------------|-------|--------|
| **Region** | US | US | ✓ | - |
| **TX Power** | 30 dBm | 30 dBm | ✓ | - |
| **Channel Num** | 20 | 20 | ✓ | - |
| **Hop Limit** | 7 | 3 | ✗ | T-Deck has shorter range |
| **Use Preset** | true | true | ✓ | - |
| **RX Boosted Gain** | true | true | ✓ | - |

## Key Differences

### 1. Channel Mismatch
- **Problem**: The T-Deck Plus lacks the secondary "jasper" channel
- **Impact**: Devices can only communicate on the primary channel (default encryption)
- **Solution**: Import the RAK4631 channel URL to the T-Deck

### 2. Hop Limit
- **RAK4631**: 7 hops (longer range, acts as infrastructure)
- **T-Deck Plus**: 3 hops (shorter range, mobile device)
- **Impact**: T-Deck messages won't travel as far through the mesh

### 3. Timezone
- **RAK4631**: PST8PDT configured
- **T-Deck Plus**: Default (no timezone set)
- **Impact**: Time stamps may differ

## Recommendations

### To Enable Full Communication:

1. **Sync Channels** - Import RAK4631's complete channel URL to T-Deck:
   ```bash
   meshtastic --seturl "https://meshtastic.org/e/#CgcSAQE6AggNCh4SEHq8k3UYS8uLF_PoID_ytw4aBmphc3BlcjoCCCASDggBOAFAB0gBUB5YFGgB"
   ```

2. **Adjust Hop Limit** (Optional) - Increase T-Deck's hop limit:
   ```bash
   meshtastic --set lora.hop_limit 7
   ```

3. **Set Timezone** (Optional) - Configure T-Deck timezone:
   ```bash
   meshtastic --set device.tzdef "PST8PDT,M3.2.0/2:00:00,M11.1.0/2:00:00"
   ```

## Security Notes

1. Both devices support PKC (Public Key Cryptography) with public keys available
2. Primary channel uses default encryption (minimal security)
3. RAK4631's secondary "jasper" channel has custom encryption
4. Serial interface is enabled on both devices

## Channel URLs

### RAK4631 Complete URL (Both Channels):
```
https://meshtastic.org/e/#CgcSAQE6AggNCh4SEHq8k3UYS8uLF_PoID_ytw4aBmphc3BlcjoCCCASDggBOAFAB0gBUB5YFGgB
```

### T-Deck Plus Current URL (Primary Only):
```
https://meshtastic.org/e/#CgcSAQE6AggNEg4IATgBQANIAVAeWBRoAQ
```

## Conclusion

The devices have compatible hardware and firmware but need channel synchronization to communicate properly. The T-Deck Plus is missing the secondary encrypted channel "jasper" that the RAK4631 has configured. After syncing the channels, both devices will be able to communicate on both the default primary channel and the encrypted secondary channel.