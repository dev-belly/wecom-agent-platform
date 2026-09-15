"""Enterprise WeChat callback signature verification and message decryption."""

from __future__ import annotations

import base64
import hashlib
import hmac
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class WeComCryptoError(ValueError):
    """Raised when a callback cannot be authenticated or decrypted."""


def verify_signature(
    token: str,
    signature: str,
    timestamp: str,
    nonce: str,
    encrypted: str,
) -> bool:
    """Verify the SHA-1 signature defined by the WeCom callback protocol."""
    if not all((token, signature, timestamp, nonce, encrypted)):
        return False
    digest = hashlib.sha1(
        "".join(sorted((token, timestamp, nonce, encrypted))).encode("utf-8"),
    ).hexdigest()
    return hmac.compare_digest(digest.encode("ascii"), signature.encode("utf-8"))


def decrypt_message(encoding_aes_key: str, encrypted: str, expected_receive_id: str) -> str:
    """Decrypt an encrypted callback and verify its CorpID/receive ID."""
    try:
        aes_key = base64.b64decode(f"{encoding_aes_key}=", validate=True)
        ciphertext = base64.b64decode(encrypted, validate=True)
    except (ValueError, TypeError) as exc:
        raise WeComCryptoError("回调密文编码无效") from exc
    if len(aes_key) != 32 or not ciphertext or len(ciphertext) % 16:
        raise WeComCryptoError("回调密钥或密文长度无效")

    decryptor = Cipher(algorithms.AES(aes_key), modes.CBC(aes_key[:16])).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    pad_size = padded[-1]
    if pad_size < 1 or pad_size > 32 or padded[-pad_size:] != bytes([pad_size]) * pad_size:
        raise WeComCryptoError("回调填充无效")
    payload = padded[:-pad_size]
    if len(payload) < 20:
        raise WeComCryptoError("回调内容不完整")

    message_length = struct.unpack(">I", payload[16:20])[0]
    message_end = 20 + message_length
    if message_end > len(payload):
        raise WeComCryptoError("回调消息长度无效")
    message = payload[20:message_end]
    receive_id = payload[message_end:]
    if expected_receive_id and not hmac.compare_digest(receive_id, expected_receive_id.encode("utf-8")):
        raise WeComCryptoError("回调接收方不匹配")
    try:
        return message.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WeComCryptoError("回调消息不是有效 UTF-8") from exc
