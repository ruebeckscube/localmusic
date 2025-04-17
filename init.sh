#!/usr/bin/env sh

# Set contents of .env as local variables
. ./.env

# A minimal config for getting SSL certificates
sh ./update_config.sh nginx_temp_cert.template

# nginx must be running, and gotta build the whole thing anyway
docker compose up --build

# Set up initial SSL certificates
docker compose run --rm  certbot certonly --webroot --webroot-path /var/www/certbot/ -d "$HOST_NAME"

# Full config that can reference the SSL certificates now that they exist
sh ./update_config.sh nginx.template

docker compose restart
