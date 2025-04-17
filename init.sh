#!/usr/bin/env sh

# Set contents of .env as local variables
. ./.env

# A minimal config for getting SSL certificates
echo "Updating nginx to temp config to get SSL certificates"
sh ./update_config.sh nginx_temp_cert.template

# nginx must be running to respond to Certificate Authority requests, and gotta build the whole thing anyway
docker compose up -d --build

echo "Docker containers are building"
while [ $(docker inspect -f '{{.State.Status}}' localmusic-proxy-1 2>/dev/null) != "running" ]
do
    sleep 1
done


echo "Setting up SSL certificates"
docker compose run --rm  certbot certonly --webroot --webroot-path /var/www/certbot/ -d "$HOST_NAME"

echo "Updating nginx config"
sh ./update_config.sh nginx.template

docker compose restart
