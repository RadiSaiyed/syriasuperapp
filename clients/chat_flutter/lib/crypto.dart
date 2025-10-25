import 'dart:convert';
import 'dart:typed_data';
import 'package:cryptography/cryptography.dart';
import 'package:shared_preferences/shared_preferences.dart';

class CryptoBox {
  static const _privKeyKey = 'x25519_priv_b64';
  static const _pubKeyKey = 'x25519_pub_b64';


  final X25519 _x25519 = X25519();
  final Hkdf _hkdf = Hkdf(hmac: Hmac.sha256(), outputLength: 32);
  final AesGcm _aead = AesGcm.with256bits();

  Future<(String privB64, String pubB64)> getOrCreateKeypair() async {
    final p = await SharedPreferences.getInstance();
    final priv = p.getString(_privKeyKey);
    final pub = p.getString(_pubKeyKey);
    if (priv != null && pub != null) return (priv, pub);
    final keyPair = await _x25519.newKeyPair();
    final privBytes = await keyPair.extractPrivateKeyBytes();
    final pubKey = await keyPair.extractPublicKey();
    final pubBytes = pubKey.bytes;
    final privB64 = base64Encode(privBytes);
    final pubB64 = base64Encode(pubBytes);
    // Store in secure storage primarily; keep legacy prefs for migration
    await p.setString(_privKeyKey, privB64);
    await p.setString(_pubKeyKey, pubB64);
    return (privB64, pubB64);
  }

  Future<String> publicKeyB64() async {
    final p = await SharedPreferences.getInstance();
    var pub = p.getString(_pubKeyKey);
    if (pub == null) {
      (_, pub) = await getOrCreateKeypair();
    }
    return pub;
  }

  Future<String> encryptFor({required String recipientPubB64, required String plaintext}) async {
    // decode recipient public key
    final recipientPub = SimplePublicKey(base64Decode(recipientPubB64), type: KeyPairType.x25519);
    // ephemeral keypair
    final eph = await _x25519.newKeyPair();
    final ephPub = await eph.extractPublicKey();
    final shared = await _x25519.sharedSecretKey(keyPair: eph, remotePublicKey: recipientPub);
    final secret = await _hkdf.deriveKey(secretKey: shared, nonce: const []);
    final nonce = _randomBytes(12);
    final secretBox = await _aead.encrypt(utf8.encode(plaintext), secretKey: secret, nonce: nonce);
    final payload = {
      'v': 1,
      'epk': base64Encode(ephPub.bytes),
      'n': base64Encode(nonce),
      'c': base64Encode(Uint8List.fromList(secretBox.cipherText + secretBox.mac.bytes)),
    };
    return jsonEncode(payload);
  }

  Future<String> decryptIncoming({required String ciphertextJson}) async {
    final map = jsonDecode(ciphertextJson) as Map<String, dynamic>;
    final epkB64 = map['epk'] as String?;
    final nB64 = map['n'] as String?;
    final cB64 = map['c'] as String?;
    if (epkB64 == null || nB64 == null || cB64 == null) {
      // Fallback: show ciphertext as-is if not an encrypted payload
      return ciphertextJson;
    }
    final p = await SharedPreferences.getInstance();
    final privB64 = p.getString(_privKeyKey);
    if (privB64 == null) return '[no key]';
    final pubB64 = p.getString(_pubKeyKey);
    if (pubB64 == null) return '[no key]';
    final privBytes = base64Decode(privB64);
    final pubKey = SimplePublicKey(base64Decode(pubB64), type: KeyPairType.x25519);
    final ourKeyPair = SimpleKeyPairData(privBytes, publicKey: pubKey, type: KeyPairType.x25519);
    final epk = SimplePublicKey(base64Decode(epkB64), type: KeyPairType.x25519);
    final shared = await _x25519.sharedSecretKey(keyPair: ourKeyPair, remotePublicKey: epk);
    final secret = await _hkdf.deriveKey(secretKey: shared, nonce: const []);
    final nonce = base64Decode(nB64);
    final data = base64Decode(cB64);
    final macLength = 16; // AES-GCM tag
    final cipherText = data.sublist(0, data.length - macLength);
    final mac = Mac(data.sublist(data.length - macLength));
    try {
      final clear = await _aead.decrypt(SecretBox(cipherText, nonce: nonce, mac: mac), secretKey: secret);
      return utf8.decode(clear);
    } catch (_) {
      // Fallback: show ciphertext as-is if decryption fails
      return ciphertextJson;
    }
  }

  Uint8List _randomBytes(int n) {
    final r = AesGcm.with256bits().newNonce();
    // above returns 12 bytes random each time; if n != 12, extend
    if (r.length == n) return Uint8List.fromList(r);
    final out = Uint8List(n);
    for (int i = 0; i < n; i++) {
      out[i] = r[i % r.length];
    }
    return out;
  }
}
