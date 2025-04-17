#!/usr/bin/env sh

# Set contents of .env as local variables
. ./.env

echo "Updating nginx to temp config to get SSL certificates"
sh ./update_config.sh nginx_temp_cert.template

# nginx must be running to respond to Certificate Authority requests, and gotta build the whole thing anyway
echo "Building Docker containers"
docker compose up -d --build

echo "Setting up SSL certificates"
docker compose run --rm  certbot certonly --webroot --webroot-path /var/www/certbot/ -d "$HOST_NAME"

echo "Updating nginx config"
sh ./update_config.sh nginx.template

docker compose restart
