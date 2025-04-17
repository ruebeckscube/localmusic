#!/usr/bin/env sh

# Find & replace, creating new config file from template
sed "s/TEMPLATE_HOST_NAME/$HOST_NAME/g" < nginx.template > nginx.conf
