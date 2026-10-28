#!/bin/bash
set -Eeuo pipefail

ORDER_DB_PASSWORD="${ORDER_DB_PASSWORD:-forge_order_local_dev}"
INVENTORY_DB_PASSWORD="${INVENTORY_DB_PASSWORD:-forge_inventory_local_dev}"

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname postgres \
  -v order_pw="$ORDER_DB_PASSWORD" \
  -v inventory_pw="$INVENTORY_DB_PASSWORD" <<'EOSQL'
SELECT format('CREATE ROLE forge_order LOGIN PASSWORD %L', :'order_pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'forge_order')\gexec
SELECT format('CREATE ROLE forge_inventory LOGIN PASSWORD %L', :'inventory_pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'forge_inventory')\gexec

SELECT 'CREATE DATABASE forge_orders OWNER forge_order'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'forge_orders')\gexec
SELECT 'CREATE DATABASE forge_inventory OWNER forge_inventory'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'forge_inventory')\gexec

SELECT 'CREATE DATABASE forge_orders_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'forge_orders_test')\gexec
SELECT 'CREATE DATABASE forge_inventory_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'forge_inventory_test')\gexec
EOSQL

echo "Forge databases and roles initialized"
