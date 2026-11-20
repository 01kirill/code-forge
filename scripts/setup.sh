#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
umask 077
mkdir -p .local/keys .local/tls
if [ ! -f .local/keys/private.pem ]; then
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out .local/keys/private.pem
fi
openssl pkey -in .local/keys/private.pem -pubout -out .local/keys/public.pem
if [ ! -f .local/tls/key.pem ]; then
    openssl req -x509 -newkey rsa:3072 -nodes -days 90 -keyout .local/tls/key.pem \
        -out .local/tls/cert.pem -subj /CN=localhost -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
fi
if [ ! -e .env ]; then
    for name in PG_PASSWORD AUTH_PASSWORD CONTEST_PASSWORD REDIS_PASSWORD RABBIT_PASSWORD \
        INTERNAL_KEY JUDGE_DB_PASSWORD JUDGE_REDIS_PASSWORD JUDGE_SECRET JUDGE_AUTH_TOKEN; do
        printf '%s=%s\n' "$name" "$(openssl rand -hex 32)"
    done > .env
fi
