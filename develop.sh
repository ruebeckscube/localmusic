#!/usr/bin/env sh

# based on a similar script from listenbrainz
# https://github.com/metabrainz/listenbrainz-server/blob/f1b2ad535c0de29f3dd3a02cc2969f1a30a58dd9/develop.sh

if [ ! -f "manage.py" ]; then
    echo "This script must be run from the top level directory of the localmusic project."
    exit -1
fi

if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    DOCKER_COMPOSE_CMD="docker-compose"
fi

if [ -f .env ]; then
    . .env
fi

invoke_docker_compose() {
    if [ "$IS_DEV" = "True" ]; then
        echo "Using development compose file."
        COMPOSE_FILE="dev-docker-compose.yml"
    else
        echo "Using production compose file."
        COMPOSE_FILE="docker-compose.yml"
    fi

    $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE \
        -p localmusic \
        --env-file .env \
        "$@"
}

invoke_manage() {
    invoke_docker_compose run  --rm web \
            python3 manage.py \
            "$@"
}

update_config() {
    echo "Updating nginx config file from ${1:-nginx.template}"
    sed "s/TEMPLATE_HOST_NAME/$HOST_NAME/g" < "${1:-nginx.template}" > nginx.conf
}

setup_initial_server() {
    update_config "nginx_temp_cert.template"

    # nginx must be running to respond to Certificate Authority requests, and gotta build the whole thing anyway
    echo "Building Docker containers"
    # invoke_docker_compose up -d --wait --build;
    invoke_docker_compose up -d --build

    echo "Setting up SSL certificates"
    invoke_docker_compose run --rm  certbot certonly --webroot --webroot-path /var/www/certbot/ -d "$HOST_NAME" -d "www.$HOST_NAME"

    update_config "nginx.template"
    invoke_docker_compose restart
}

# Arguments following "manage" are passed to manage.py inside a new web container.
if [ "$1" = "manage" ]; then shift
    echo "Running manage.py..."
    invoke_manage "$@"
elif [ "$1" = "update-config" ]; then shift
    update_config "$@"
elif [ "$1" = "init" ]; then
    setup_initial_server
else
    echo "Running docker-compose with the given command..."
    invoke_docker_compose "$@"
fi
