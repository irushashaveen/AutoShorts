#!/usr/bin/env bash
# ==============================================================================
# AutoShorts Oracle Cloud Deployment: Let's Encrypt SSL Bootstrap Script
# Target Subdomain: shorts.reccalab.com
# ==============================================================================

set -euo pipefail

DOMAIN="shorts.reccalab.com"
EMAIL="admin@reccalab.com"

echo "=== AutoShorts SSL Certificate Bootstrap for ${DOMAIN} ==="

# 1. Ensure Certbot directories exist
mkdir -p ./data/certbot/conf
mkdir -p ./data/certbot/www

# 2. Check if certificate already exists
if [ -d "./data/certbot/conf/live/${DOMAIN}" ]; then
    echo "✅ SSL certificate for ${DOMAIN} already exists."
    exit 0
fi

# 3. Create dummy self-signed certificate temporarily so Nginx can start
echo "Generating temporary self-signed certificate for Nginx initial boot..."
mkdir -p "./data/certbot/conf/live/${DOMAIN}"
openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "./data/certbot/conf/live/${DOMAIN}/privkey.pem" \
    -out "./data/certbot/conf/live/${DOMAIN}/fullchain.pem" \
    -subj "/CN=localhost"

# 4. Start Nginx
echo "Starting Nginx reverse proxy..."
docker compose up -d nginx

# 5. Delete temporary dummy certificate
rm -rf "./data/certbot/conf/live/${DOMAIN}"

# 6. Request official certificate from Let's Encrypt via Certbot
echo "Requesting official Let's Encrypt certificate for ${DOMAIN}..."
docker compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    --email ${EMAIL} \
    -d ${DOMAIN} \
    --rsa-key-size 4096 \
    --agree-tos \
    --force-renewal \
    --non-interactive" certbot

# 7. Reload Nginx with official certificate
echo "Reloading Nginx with production TLS certificate..."
docker compose exec nginx nginx -s reload

echo "=== SSL setup complete for https://${DOMAIN} ==="
