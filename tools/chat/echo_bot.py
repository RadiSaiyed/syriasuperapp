#!/usr/bin/env python3
import os, time, json, base64, sys
import requests

BASE = os.environ.get('CHAT_BASE_URL', 'http://localhost:8091').rstrip('/')
PHONE = os.environ.get('CHAT_BOT_PHONE', '+963900000002')
NAME = os.environ.get('CHAT_BOT_NAME', 'Demo Bot')

def get_token():
    # dev OTP flow
    try:
        requests.post(f"{BASE}/auth/request_otp", json={'phone': PHONE}, timeout=5)
    except Exception:
        pass
    r = requests.post(f"{BASE}/auth/verify_otp", json={'phone': PHONE, 'otp': '123456', 'name': NAME}, timeout=8)
    r.raise_for_status()
    return r.json()['access_token']

def auth_h(token):
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

def publish_key(token):
    try:
        pub = base64.b64encode(os.urandom(32)).decode()
        requests.post(f"{BASE}/keys/publish", headers=auth_h(token), json={'public_key': pub, 'device_name': NAME}, timeout=5)
    except Exception:
        pass

def echo_loop(token):
    print(f"[echo-bot] Running against {BASE} as {PHONE}")
    while True:
        try:
            # Poll inbox for pending messages to me
            r = requests.get(f"{BASE}/messages/inbox", headers=auth_h(token), timeout=15)
            if r.status_code == 401:
                token = get_token()
                continue
            r.raise_for_status()
            msgs = r.json().get('messages') or []
            for m in msgs:
                msg_id = m.get('id')
                sender = m.get('sender_user_id')
                ct = (m.get('ciphertext') or '').strip()
                # Simple echo
                reply = f"[Bot] You said: {ct[:160]}"
                body = {
                    'recipient_user_id': sender,
                    'sender_device_id': 'echo-bot',
                    'ciphertext': reply,
                }
                try:
                    requests.post(f"{BASE}/messages/send", headers=auth_h(token), json=body, timeout=8)
                except Exception:
                    pass
                # Ack delivered to clear from inbox
                try:
                    requests.post(f"{BASE}/messages/{msg_id}/ack_delivered", headers=auth_h(token), timeout=5)
                except Exception:
                    pass
        except Exception:
            time.sleep(2)
        time.sleep(1.5)

def main():
    token = get_token()
    publish_key(token)
    echo_loop(token)

if __name__ == '__main__':
    main()

