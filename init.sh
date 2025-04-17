#!/usr/bin/env sh

# Set contents of .env as local variables
. ./.env

sh ./update_config.sh

# Set up initial SSL certificates
docker compose run --rm  certbot certonly --webroot --webroot-path /var/www/certbot/ -d "$HOST_NAME"
