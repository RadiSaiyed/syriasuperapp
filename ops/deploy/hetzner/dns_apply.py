#!/usr/bin/env python3
import os
import sys
import json
from typing import Optional, Dict, Any, List
from urllib import request, parse, error

API = "https://dns.hetzner.com/api/v1"

def api_call(method: str, path: str, token: str, data: Optional[Dict[str, Any]] = None):
    url = f"{API}{path}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Auth-API-Token": token,
    }
    body = None
    if data is not None:
        body = json.dumps(data).encode()
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as e:
        msg = e.read().decode()
        print(f"[hetzner-dns] HTTP {e.code} {e.reason}: {msg}", file=sys.stderr)
        raise

def get_zone(token: str, base_domain: str) -> Optional[Dict[str, Any]]:
    try:
        data = api_call("GET", f"/zones?name={parse.quote(base_domain)}", token)
        zones = data.get("zones", [])
        return zones[0] if zones else None
    except error.HTTPError as e:
        if e.code == 404:
            return None
        raise

def create_zone(token: str, base_domain: str, ttl: int) -> Dict[str, Any]:
    payload = {"name": base_domain, "ttl": ttl}
    resp = api_call("POST", "/zones", token, payload)
    zone = resp.get("zone", resp)
    ns = zone.get("name_servers") or []
    print(f"[hetzner-dns] Zone created: {base_domain}")
    if ns:
        print("[hetzner-dns] Nameservers:")
        for n in ns:
            print(f"  - {n}")
    return zone

def find_records(token: str, zone_id: str, name: str, rtype: str):
    data = api_call("GET", f"/records?zone_id={parse.quote(zone_id)}", token)
    recs = [r for r in data.get("records", []) if r.get("type") == rtype and r.get("name") == name]
    return recs

def upsert_record(token: str, zone_id: str, name: str, rtype: str, value: str, ttl: int):
    existing = find_records(token, zone_id, name, rtype)
    if existing:
        rec = existing[0]
        if rec.get("value") == value and int(rec.get("ttl", ttl)) == ttl:
            print(f"[hetzner-dns] {rtype} {name} unchanged -> {value}")
            return rec
        # update first
        upd = {
            "id": rec["id"],
            "value": value,
            "ttl": ttl,
            "type": rtype,
            "name": name,
            "zone_id": zone_id,
        }
        resp = api_call("PUT", "/records/{id}".format(id=rec["id"]), token, upd)
        print(f"[hetzner-dns] {rtype} {name} updated -> {value}")
        # delete any duplicates
        for extra in existing[1:]:
            api_call("DELETE", f"/records/{extra['id']}", token)
            print(f"[hetzner-dns] {rtype} {name} removed duplicate id={extra['id']}")
        return resp.get("record", upd)
    else:
        payload = {
            "value": value,
            "ttl": ttl,
            "type": rtype,
            "name": name,
            "zone_id": zone_id,
        }
        resp = api_call("POST", "/records", token, payload)
        print(f"[hetzner-dns] {rtype} {name} created -> {value}")
        return resp.get("record", payload)

def main(argv):
    hostnames = argv[1:] if len(argv) > 1 else ["payments", "taxi"]
    token = os.environ.get("HETZNER_DNS_API_TOKEN", "").strip()
    if token == "REPLACE_ME":
        token = ""
    base_domain = os.environ.get("BASE_DOMAIN", "").strip()
    ipv4 = os.environ.get("HETZNER_IPV4", "").strip()
    ipv6 = os.environ.get("HETZNER_IPV6", "").strip()
    ttl = int(os.environ.get("DNS_TTL", "300"))

    if not token:
        raise SystemExit("HETZNER_DNS_API_TOKEN not set in environment")
    if not base_domain:
        raise SystemExit("BASE_DOMAIN not set in environment")
    if not ipv4 and not ipv6:
        raise SystemExit("HETZNER_IPV4 or HETZNER_IPV6 must be set")

    zone = get_zone(token, base_domain)
    if zone is None:
        if os.environ.get("MANAGE_ZONE", "").lower() in ("1", "true", "yes"):
            zone = create_zone(token, base_domain, ttl)
        else:
            raise SystemExit(f"Zone {base_domain} not found. Set MANAGE_ZONE=1 to create it or ensure token has access.")
    zone_id = zone["id"]
    for h in hostnames:
        name = f"{h}.{base_domain}"
        rel = f"{h}"
        if ipv4:
            upsert_record(token, zone_id, rel, "A", ipv4, ttl)
        if ipv6:
            upsert_record(token, zone_id, rel, "AAAA", ipv6, ttl)
    print("[hetzner-dns] Done")

if __name__ == "__main__":
    main(sys.argv)
