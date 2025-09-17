# Meshtastic Direct Message (DM) Encryption Deep Dive

## Executive Summary

After analyzing the Meshtastic source code, I've discovered that DM encryption issues you're experiencing are likely due to **Public Key Infrastructure (PKI)** implementation complexities. The system uses **Curve25519** for key exchange and **AES-CCM** for message encryption, but there are several failure points that can prevent successful decryption.

## How Meshtastic PKI/DM Encryption Works

### 1. Key Generation & Distribution

Each node generates a **Curve25519 key pair**:
- **Private Key**: 32 bytes, stored locally in `config.security.private_key`
- **Public Key**: 32 bytes, shared with network via NodeInfo packets

```cpp
// From CryptoEngine.cpp
void CryptoEngine::generateKeyPair(uint8_t *pubKey, uint8_t *privKey) {
    Curve25519::dh1(public_key, private_key);
}
```

### 2. Encryption Process (Sender Side)

When sending a DM to a specific node:

```cpp
// From Router.cpp (line 574-598)
if (config.security.private_key.size == 32 &&     // Sender has private key
    !isBroadcast(p->to) &&                        // Not a broadcast
    node->user.public_key.size == 32) {           // Recipient has public key

    // Perform ECDH key agreement
    crypto->encryptCurve25519(
        p->to,                          // Destination node ID
        getFrom(p),                     // Sender node ID
        node->user.public_key,          // Recipient's public key
        p->id,                          // Packet ID (used in nonce)
        numbytes,                       // Payload size
        bytes,                          // Plaintext
        p->encrypted.bytes              // Output ciphertext
    );

    p->channel = 0;                     // Channel 0 = PKI encrypted
    p->pki_encrypted = true;            // Mark as PKI encrypted
}
```

### 3. The Actual Encryption (ECDH + AES-CCM)

```cpp
// From CryptoEngine.cpp
bool CryptoEngine::encryptCurve25519(...) {
    // 1. Generate random nonce
    long extraNonceTmp = random();

    // 2. Perform ECDH: sender_private × recipient_public = shared_secret
    if (!crypto->setDHPublicKey(remotePublic.bytes))
        return false;

    // 3. Hash the shared secret with SHA256
    crypto->hash(shared_key, 32);

    // 4. Create full nonce: fromNode + packetId + randomNonce
    initNonce(fromNode, packetNum, extraNonceTmp);

    // 5. Encrypt with AES-CCM (includes 8-byte auth tag)
    aes_ccm_ae(shared_key, 32, nonce, 8,
               bytes, numBytes,             // plaintext
               nullptr, 0,                   // no additional data
               bytesOut,                     // ciphertext output
               auth);                        // auth tag output

    // 6. Append random nonce to ciphertext (needed for decryption)
    memcpy(auth + 8, &extraNonceTmp, sizeof(uint32_t));
}
```

**Result**: Ciphertext + 12 bytes overhead (8-byte auth tag + 4-byte random nonce)

### 4. Decryption Process (Receiver Side)

```cpp
// From Router.cpp (line 372-401)
if (p->channel == 0 &&                           // Channel 0 = PKI encrypted
    isToUs(p) &&                                 // Addressed to us
    nodeDB->getMeshNode(p->from)->user.public_key.size > 0) {  // Sender has public key

    // Attempt PKI decryption
    if (crypto->decryptCurve25519(
        p->from,                                 // Sender node ID
        nodeDB->getMeshNode(p->from)->user.public_key,  // Sender's public key
        p->id,                                   // Packet ID (for nonce)
        rawSize,                                 // Ciphertext size
        p->encrypted.bytes,                      // Ciphertext
        bytes)) {                                // Output plaintext

        // Decode the decrypted protobuf
        if (pb_decode_from_bytes(bytes, rawSize - MESHTASTIC_PKC_OVERHEAD,
                                 &meshtastic_Data_msg, &decodedtmp)) {
            p->pki_encrypted = true;
            p->decoded = decodedtmp;
            // Success!
        }
    }
}
```

### 5. The Actual Decryption

```cpp
// From CryptoEngine.cpp
bool CryptoEngine::decryptCurve25519(...) {
    // 1. Extract random nonce from end of ciphertext
    const uint8_t *auth = bytes + numBytes - 12;
    uint32_t extraNonce;
    memcpy(&extraNonce, auth + 8, sizeof(uint32_t));

    // 2. Perform ECDH: receiver_private × sender_public = shared_secret
    if (!crypto->setDHPublicKey(remotePublic.bytes))
        return false;

    // 3. Hash the shared secret with SHA256
    crypto->hash(shared_key, 32);

    // 4. Recreate nonce: fromNode + packetId + extractedNonce
    initNonce(fromNode, packetNum, extraNonce);

    // 5. Decrypt with AES-CCM and verify auth tag
    return aes_ccm_ad(shared_key, 32, nonce, 8,
                     bytes, numBytes - 12,        // ciphertext
                     nullptr, 0,                   // no additional data
                     auth,                         // auth tag to verify
                     bytesOut);                    // plaintext output
}
```

## Why DM Decryption Fails

### 1. **Missing or Invalid Public Keys**

The most common issue is that nodes don't have each other's public keys:

```python
# Your Python code shows this warning:
WARNING:backend.meshtastic_connector:⚠️ Received encrypted packet that couldn't be decoded - likely PKC DM with key issues
```

**Causes**:
- Node hasn't sent a NodeInfo packet with its public key
- Public key was corrupted in transmission
- Node database doesn't have the sender's key stored

**Solution in your pkc_key_manager.py**:
```python
def handle_node_info(self, node_id: str, public_key: bytes):
    """Store public keys as they arrive"""
    if public_key and len(public_key) == 32:
        self.public_keys[node_id] = public_key
        self.save_keys()  # Persist to disk
```

### 2. **Channel Mismatch**

PKI encrypted messages use **channel 0** as a special marker:

```cpp
p->channel = 0;  // This means "PKI encrypted"
```

If your code expects messages on a different channel, it won't try PKI decryption.

### 3. **Key Synchronization Issues**

The ECDH shared secret must be identical on both sides:
- **Sender**: `sender_private × recipient_public = shared_secret`
- **Receiver**: `receiver_private × sender_public = shared_secret`

If either public key is wrong/outdated, decryption fails silently.

### 4. **Nonce Reconstruction Failure**

The nonce has three parts:
```cpp
void initNonce(uint32_t fromNode, uint64_t packetId, uint32_t extraNonce) {
    memcpy(nonce, &fromNode, sizeof(fromNode));      // 4 bytes
    memcpy(nonce + 4, &packetId, sizeof(packetId));   // 8 bytes
    memcpy(nonce + 12, &extraNonce, sizeof(extraNonce)); // 4 bytes
}
```

If any part is wrong (especially the random nonce), decryption fails.

### 5. **Authentication Tag Failure**

AES-CCM provides authenticated encryption. If the auth tag doesn't match (due to corruption or wrong key), decryption returns false.

## Python Library Limitations

The Python library **doesn't do encryption/decryption itself**:

```python
# From mesh_interface.py
def sendData(..., pkiEncrypted=False, publicKey=None):
    # Just sets flags for the device to handle
    meshPacket.pki_encrypted = pkiEncrypted
    meshPacket.public_key = publicKey
    # Device firmware does actual encryption
```

This means:
- **Encryption happens in firmware** before transmission
- **Decryption happens in firmware** after reception
- **Python only sees plaintext** (if successful) or encrypted bytes (if failed)

## Your Server-Side Solution

Since the Python library can't decrypt PKI messages, your server needs to:

### 1. **Track Public Keys Aggressively**

```python
class EnhancedPKCManager:
    def __init__(self):
        self.public_keys = {}  # node_id -> public_key
        self.key_update_times = {}  # Track when keys were last seen

    def request_missing_keys(self):
        """Proactively request NodeInfo for nodes without keys"""
        for node_id in self.get_nodes_without_keys():
            self.meshtastic.requestNodeInfo(node_id)

    def validate_key(self, public_key: bytes) -> bool:
        """Ensure key is valid Curve25519 point"""
        if len(public_key) != 32:
            return False
        # Check for weak/invalid keys
        if all(b == 0 for b in public_key):
            return False
        return True
```

### 2. **Implement Fallback Strategies**

```python
class DMFallbackHandler:
    def handle_failed_dm(self, packet):
        """When PKI decryption fails"""

        # Strategy 1: Request fresh NodeInfo
        if self.should_refresh_key(packet.from_id):
            self.request_node_info(packet.from_id)
            self.queue_for_retry(packet)

        # Strategy 2: Try legacy decryption (pre-PKI)
        if self.try_channel_key_decryption(packet):
            return True

        # Strategy 3: Store encrypted for later
        self.store_encrypted_message(packet)

        # Strategy 4: Request sender to resend
        if self.can_request_resend(packet.from_id):
            self.send_resend_request(packet.id)
```

### 3. **Monitor PKI Health**

```python
class PKIHealthMonitor:
    def analyze_pki_success_rate(self):
        total_dms = self.count_dm_attempts()
        successful = self.count_successful_decrypts()
        failed = self.count_failed_decrypts()

        if failed / total_dms > 0.2:  # >20% failure rate
            self.trigger_key_refresh_for_all_nodes()

    def diagnose_pki_issues(self, failed_packet):
        issues = []

        # Check if we have sender's public key
        if not self.has_public_key(failed_packet.from_id):
            issues.append("Missing sender public key")

        # Check if sender might have our key
        if not self.sent_node_info_recently(failed_packet.from_id):
            issues.append("Sender might not have our public key")

        # Check key age
        key_age = self.get_key_age(failed_packet.from_id)
        if key_age > timedelta(days=7):
            issues.append("Public key is stale")

        return issues
```

### 4. **Force Key Exchange Protocol**

```python
class ForceKeyExchange:
    async def ensure_key_exchange(self, target_node_id):
        """Ensure both nodes have each other's keys"""

        # Step 1: Send our NodeInfo with public key
        await self.meshtastic.sendNodeInfo(
            destinationId=target_node_id,
            includePublicKey=True
        )

        # Step 2: Request their NodeInfo
        await asyncio.sleep(2)  # Give time for processing
        await self.meshtastic.requestNodeInfo(target_node_id)

        # Step 3: Wait for response
        key = await self.wait_for_public_key(target_node_id, timeout=10)

        if key:
            # Step 4: Send test DM to verify
            success = await self.send_test_dm(target_node_id)
            return success

        return False
```

## Immediate Fixes for Your Implementation

### 1. **Add PKI Diagnostics Endpoint**

```python
@app.get("/api/pki/status")
async def get_pki_status():
    return {
        "nodes_with_keys": len([n for n in nodes if n.public_key]),
        "nodes_without_keys": len([n for n in nodes if not n.public_key]),
        "failed_dm_count": state.failed_dm_count,
        "successful_dm_count": state.successful_dm_count,
        "key_request_queue": state.pending_key_requests
    }
```

### 2. **Automatic Key Request on DM Failure**

```python
# In your meshtastic_connector.py
def handle_encrypted_packet(self, packet):
    if packet.get('channel') == 0:  # PKI encrypted
        sender_id = packet.get('from')

        # Check if we have sender's key
        if sender_id not in self.public_keys:
            logger.info(f"Missing public key for {sender_id}, requesting...")
            self.request_node_info(sender_id)

            # Queue packet for retry after getting key
            self.pending_encrypted_packets[sender_id].append(packet)
```

### 3. **Periodic Key Refresh**

```python
async def periodic_key_refresh():
    """Run every hour to refresh stale keys"""
    while True:
        await asyncio.sleep(3600)  # 1 hour

        for node_id, last_update in key_update_times.items():
            if time.time() - last_update > 86400:  # 24 hours
                await request_node_info(node_id)
```

## Conclusion

The PKI system in Meshtastic is robust but requires careful key management. Your server can't decrypt messages itself (firmware handles that), but it can:

1. **Aggressively collect and manage public keys**
2. **Detect when decryption fails** (channel 0 with encrypted payload)
3. **Trigger key exchanges** when needed
4. **Queue and retry** failed messages after obtaining keys
5. **Monitor PKI health** and alert on high failure rates

The root cause of your DM decryption issues is likely **missing or outdated public keys** in the node database. Implement aggressive key collection and refresh strategies to minimize these failures.