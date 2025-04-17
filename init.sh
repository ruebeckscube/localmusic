#!/usr/bin/env sh

. ./.env

sed "s/TEMPLATE_HOST_NAME/$HOST_NAME/g" < nginx.template > nginx.conf
