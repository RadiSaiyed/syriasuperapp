#!/usr/bin/env bash
set -euo pipefail

COMMERCE_BASE=${COMMERCE_BASE:-http://localhost:8083}

log(){ echo -e "[commerce-seed] $*"; }

token(){
  local phone=$1 name=${2:-Seed}
  curl -s -X POST "$COMMERCE_BASE/auth/request_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\"}" >/dev/null || true
  curl -s -X POST "$COMMERCE_BASE/auth/verify_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\",\"otp\":\"123456\",\"name\":\"$name\"}" | python3 - "$@" <<'PY'
import sys, json
print(json.load(sys.stdin).get('access_token',''))
PY
}

first_id(){
  python3 - "$@" <<'PY'
import sys, json
data=json.load(sys.stdin)
if isinstance(data, list) and data:
  print(data[0].get('id',''))
elif isinstance(data, dict) and 'id' in data:
  print(data['id'])
else:
  print('')
PY
}

main(){
  log "Health: $(curl -s "$COMMERCE_BASE/health" || echo 'down')"

  # Customer auth
  CUST_PHONE=${CUST_PHONE:-+963930000001}
  TOK=$(token "$CUST_PHONE" "Customer")
  H="Authorization: Bearer $TOK"

  # Trigger dev seed and fetch a shop
  log "Fetching shops (triggers dev seed on first call)…"
  SHOPS_JSON=$(curl -s "$COMMERCE_BASE/shops" -H "$H")
  SHOP_ID=$(echo "$SHOPS_JSON" | first_id)
  if [ -z "$SHOP_ID" ]; then
    echo "No shop id found" >&2; exit 1
  fi
  log "Shop=$SHOP_ID"

  # List products and add two to cart
  PRODS_JSON=$(curl -s "$COMMERCE_BASE/shops/$SHOP_ID/products" -H "$H")
  P1=$(echo "$PRODS_JSON" | python3 - <<'PY'
import sys, json
data=json.load(sys.stdin)
print(data[0]['id'] if isinstance(data,list) and len(data)>0 else '')
PY
)
  P2=$(echo "$PRODS_JSON" | python3 - <<'PY'
import sys, json
data=json.load(sys.stdin)
print(data[1]['id'] if isinstance(data,list) and len(data)>1 else '')
PY
)
  [ -n "$P1" ] && curl -s -X POST "$COMMERCE_BASE/cart/items" -H "$H" -H 'Content-Type: application/json' --data "{\"product_id\":\"$P1\",\"qty\":1}" >/dev/null
  [ -n "$P2" ] && curl -s -X POST "$COMMERCE_BASE/cart/items" -H "$H" -H 'Content-Type: application/json' --data "{\"product_id\":\"$P2\",\"qty\":2}" >/dev/null
  CART=$(curl -s "$COMMERCE_BASE/cart" -H "$H")
  log "Cart: $CART"

  # Checkout
  ORDER_JSON=$(curl -s -X POST "$COMMERCE_BASE/orders/checkout" -H "$H" -H 'Content-Type: application/json' --data '{"shipping_name":"John Doe","shipping_phone":"+963930000001","shipping_address":"Damascus, Main St"}')
  OID=$(echo "$ORDER_JSON" | first_id)
  log "Order: $OID"
  if [ -n "$OID" ]; then
    # Mark paid + shipped (dev helpers)
    curl -s -X POST "$COMMERCE_BASE/orders/$OID/mark_paid" -H "$H" >/dev/null || true
    curl -s -X POST "$COMMERCE_BASE/orders/$OID/mark_shipped" -H "$H" >/dev/null || true
  fi
  log "Done."
}

main "$@"

