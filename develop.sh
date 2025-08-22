#!/usr/bin/env bash

# based on a similar script from listenbrainz
# https://github.com/metabrainz/listenbrainz-server/blob/f1b2ad535c0de29f3dd3a02cc2969f1a30a58dd9/develop.sh

if [ ! -f "manage.py" ]; then
    echo "This script must be run from the top level directory of the localmusic project."
    exit 1
fi

if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    DOCKER_COMPOSE_CMD="docker-compose"
fi

if [ ! -e ".env" ]; then
    echo "No .env file found"
    exit 1
fi

# Load env variables, mostly for IS_DEV
. ./.env


if [ "$IS_DEV" = "True" ]; then
    COMPOSE_FILE="docker-compose-dev.yml"
    echo "Using development compose file."
else
    COMPOSE_FILE="docker-compose-prod.yml"
    echo "Using production compose file."
fi

invoke_docker_compose() {
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

    invoke_manage update_musicbrainz_data
}

dump_data() {
    echo "Exporting database to ${1:-datadump.json}"
    invoke_manage dumpdata \
        --natural-foreign --natural-primary \
        -e contenttypes -e auth.Permission -e admin -e sessions \
        -e findshows.MusicBrainzArtist \
        --indent 4 \
        > "${1:-datadump.json}"
}

load_data() {
    DATABASE_FILE="${1:-datadump.json}"
    echo "Importing database from $DATABASE_FILE"
    invoke_docker_compose cp "$DATABASE_FILE" web:/app/temp_database_file.json
    # invoke_manage loaddata /app/temp_database_file.json
    invoke_docker_compose run --rm web sh -c "python3 manage.py loaddata /app/temp_database_file.json && rm /app/temp_database_file.json"
}

check_for_backup_dir() {
    if [ -z "$BACKUP_DIR" ]; then
        echo "failed: missing BACKUP_DIR in env file."
        exit
    fi
    if [ ! -d "$BACKUP_DIR" ]; then
        echo "failed: $BACKUP_DIR does not exist; make directory or edit BACKUP_DIR in env file."
        exit
    fi
}

backup() {
    check_for_backup_dir
    TODAY=$(date +"%F")
    TODAY_DIR="$BACKUP_DIR/$TODAY"

    mkdir "$TODAY_DIR"
    echo
    echo "Exporting database"
    dump_data "$TODAY_DIR/database.json"
    echo
    echo "Copying media files"
    invoke_docker_compose cp web:/app/media "$TODAY_DIR/"
    echo
    DELETE_DATE=$(date -v "-2d" +"%F")
    echo "Deleting backups from $DELETE_DATE and older"
    CUTOFF=$((${#BACKUP_DIR} + 2))
    for d in "$BACKUP_DIR"/*; do
        DATE=$(echo "$d" | cut -c "$CUTOFF-")
        if [[ ! "$DATE" > "$DELETE_DATE" ]]; then
            echo "removed $d"
            rm -rf "$d"
        fi
    done
}

load_backup() {
    check_for_backup_dir
    echo "Available backups:"
    ls "$BACKUP_DIR"
    printf "Enter date to restore backup from: "
    read -r DATE
    DATE_DIR="$BACKUP_DIR/$DATE"
    if [ ! -d "$DATE_DIR" ]; then
        echo "failed: $DATE_DIR does not exist"
        exit
    fi
    echo
    echo "Restoring database"
    load_data "$DATE_DIR/database.json"
    echo
    echo "Restoring media files"
    invoke_docker_compose cp "$DATE_DIR/media" web:/app/
    echo
    echo "Successfully restored from backup"

}

coverage_report() {
    if [ "$IS_DEV" = "True" ]; then
        invoke_docker_compose run --rm web sh -c "coverage run ./manage.py test && coverage html"
        open htmlcov/index.html
    else
        echo "Don't run coverage/tests in prod."
    fi
}

connect_to_database() {
    psql "postgresql://$DATABASE_USER:$DATABASE_PASSWORD@localhost:5431/$DATABASE_NAME"
}

update_app() {
    git pull
    invoke_docker_compose up --build -d
}

nightly_tasks() {
    echo
    date
    echo "MOD REMINDER"
    invoke_manage send_mod_reminder
    echo "BACKUP"
    backup
    echo "UPDATING APP"
    update_app
}

weekly_tasks() {
    echo
    date
    echo "SENDING WEEKLY EMAIL"
    invoke_manage send_weekly_recs
}

biweekly_tasks() {
    echo
    date
    echo "RENEWING SSL CERTICFICATES"
    invoke_docker_compose run --rm certbot renew
    echo "UPDATING MUSICBRAINZ DATA"
    invoke_manage update_musicbrainz_data
}

# Arguments following "manage" are passed to manage.py inside a new web container.
if [ "$1" = "manage" ]; then shift
    echo "Running manage.py..."
    invoke_manage "$@"
elif [ "$1" = "update-config" ]; then shift
    update_config "$@"
elif [ "$1" = "init" ]; then
    setup_initial_server
elif [ "$1" = "nightly-tasks" ]; then
    biweekly_tasks
elif [ "$1" = "weekly-tasks" ]; then
    biweekly_tasks
elif [ "$1" = "biweekly-tasks" ]; then
    biweekly_tasks
elif [ "$1" = "dump-data" ]; then shift
    dump_data "$@"
elif [ "$1" = "load-data" ]; then shift
    load_data "$@"
elif [ "$1" = "backup" ]; then shift
    backup "$@"
elif [ "$1" = "load-backup" ]; then shift
    load_backup "$@"
elif [ "$1" = "coverage" ]; then
    coverage_report
elif [ "$1" = "psql" ]; then
    connect_to_database
else
    echo "Running docker-compose with the given command..."
    invoke_docker_compose "$@"
fi
