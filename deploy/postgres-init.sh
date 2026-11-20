#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  --set=auth_password="$AUTH_PASSWORD" --set=contest_password="$CONTEST_PASSWORD" <<'SQL'
CREATE ROLE auth LOGIN PASSWORD :'auth_password';
CREATE ROLE contest LOGIN PASSWORD :'contest_password';
CREATE DATABASE auth OWNER auth;
CREATE DATABASE contest OWNER contest;
REVOKE CONNECT ON DATABASE auth FROM PUBLIC;
REVOKE CONNECT ON DATABASE contest FROM PUBLIC;
SQL
