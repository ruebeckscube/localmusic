#!/usr/bin/env sh

# Set contents of .env as local variables
. ./.env

# Find & replace, creating new config file from template
sed "s/TEMPLATE_HOST_NAME/$HOST_NAME/g" < nginx.template > nginx.conf
