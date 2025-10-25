#!/usr/bin/env bash
set -euo pipefail

FOOD_BASE=${FOOD_BASE:-http://localhost:8090}

log(){ echo -e "[food-seed] $*"; }

# Ensure minimal schema changes for latest code (idempotent)
ensure_db_migration(){
  if command -v docker >/dev/null 2>&1; then
    if docker ps --format '{{.Names}}' | grep -q '^food-db-1$'; then
      log "Ensuring DB migration (food_operator_members table)…"
      docker exec -i food-db-1 psql -U postgres -d food <<'SQL'
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='food_operator_members') THEN
    CREATE TABLE food_operator_members (
      id uuid PRIMARY KEY,
      user_id uuid NOT NULL REFERENCES users(id),
      role VARCHAR(32) NOT NULL DEFAULT 'admin',
      created_at TIMESTAMP NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS ix_food_operator_members_user ON food_operator_members(user_id);
  END IF;
END $$;
SQL
    fi
  fi
}

token(){
  local phone=$1
  curl -s -X POST "$FOOD_BASE/auth/request_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\"}" >/dev/null || true
  curl -s -X POST "$FOOD_BASE/auth/verify_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\",\"otp\":\"123456\",\"name\":\"Seed\"}" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p'
}

create_restaurant(){
  local op_tok=$1 name=$2 city=$3 address=$4 owner_phone=$5
  curl -s -X POST "$FOOD_BASE/operator/restaurants" -H "Authorization: Bearer $op_tok" --get --data-urlencode "name=$name" --data-urlencode "city=$city" --data-urlencode "address=$address" --data-urlencode "owner_phone=$owner_phone" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p'
}

create_menu(){
  local owner_tok=$1 rest_id=$2 name=$3 price=$4 desc=$5
  curl -s -X POST "$FOOD_BASE/admin/restaurants/$rest_id/menu" -H "Authorization: Bearer $owner_tok" --get --data-urlencode "name=$name" --data-urlencode "price_cents=$price" --data-urlencode "description=$desc" >/dev/null
}

main(){
  ensure_db_migration || true

  log "Health: $(curl -s $FOOD_BASE/health)"

  OP_PHONE=${OP_PHONE:-+963900000010}
  OP_TOK=$(token "$OP_PHONE")
  curl -s -X POST "$FOOD_BASE/operator/dev/become_admin" -H "Authorization: Bearer $OP_TOK" >/dev/null || true

  log "Seeding restaurants + menus via operator + owner APIs…"
  # Demo owners
  OWNER1=${OWNER1:-+963900000301}
  OWNER2=${OWNER2:-+963900000302}

  # Damascus Eats
  R1=$(create_restaurant "$OP_TOK" "Damascus Eats" Damascus "Main St 1, Damascus" "$OWNER1")
  O1_TOK=$(token "$OWNER1")
  create_menu "$O1_TOK" "$R1" "Shawarma" 15000 "Chicken shawarma wrap"
  create_menu "$O1_TOK" "$R1" "Falafel" 8000 "Crispy falafel"

  # Aleppo Grill
  R2=$(create_restaurant "$OP_TOK" "Aleppo Grill" Aleppo "Citadel Rd 10, Aleppo" "$OWNER2")
  O2_TOK=$(token "$OWNER2")
  create_menu "$O2_TOK" "$R2" "Kebab Plate" 22000 "Mixed kebabs"
  create_menu "$O2_TOK" "$R2" "Hummus" 7000 "With olive oil"

  # Latakia Seafood
  R3=$(create_restaurant "$OP_TOK" "Latakia Seafood" Latakia "Seaside Ave 5, Latakia" "$OWNER2")
  create_menu "$O2_TOK" "$R3" "Grilled Fish" 35000 "Daily catch"
  create_menu "$O2_TOK" "$R3" "Shrimp Plate" 42000 "Garlic butter"

  log "Done. Restaurants: $R1 $R2 $R3"
}

main "$@"

