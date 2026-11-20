#!/usr/bin/env bash
set -euo pipefail

create_service_database() {
    local database_name="$1"
    local database_user="$2"
    local database_password="$3"

    psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 \
        --set=database_name="$database_name" \
        --set=database_user="$database_user" \
        --set=database_password="$database_password" <<-'EOSQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'database_user', :'database_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'database_user')
\gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'database_name', :'database_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'database_name')
\gexec
EOSQL
}

create_service_database "${USER_DB_NAME:?USER_DB_NAME is required}" \
    "${USER_DB_USER:?USER_DB_USER is required}" \
    "${USER_DB_PASSWORD:?USER_DB_PASSWORD is required}"
create_service_database "${BUDGET_DB_NAME:?BUDGET_DB_NAME is required}" \
    "${BUDGET_DB_USER:?BUDGET_DB_USER is required}" \
    "${BUDGET_DB_PASSWORD:?BUDGET_DB_PASSWORD is required}"
create_service_database "${REPORT_DB_NAME:?REPORT_DB_NAME is required}" \
    "${REPORT_DB_USER:?REPORT_DB_USER is required}" \
    "${REPORT_DB_PASSWORD:?REPORT_DB_PASSWORD is required}"
