#!/usr/bin/env bash

# based on a similar script from listenbrainz
# https://github.com/metabrainz/listenbrainz-server/blob/f1b2ad535c0de29f3dd3a02cc2969f1a30a58dd9/develop.sh

if [ ! -f "README.md" ]; then
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
    COMPOSE_FILE="docker-compose/dev.yml"
    echo "Using development compose file."
else
    COMPOSE_FILE="docker-compose/prod.yml"
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
    echo "Updating nginx config file from ${1:-config/nginx.template}"
    sed "s=TEMPLATE_HOST_NAME=$HOST_NAME=g" < "${1:-config/nginx.template}" > config/nginx.conf

    echo "Updating logrotate config from config/logrotate.template"
    sed "s=TEMPLATE_DIRECTORY_NAME=$(pwd)=g" < config/logrotate.template > config/logrotate.conf
}

setup_initial_server() {
    update_config "config/nginx_temp_cert.template"
    mkdir "$BACKUP_DIR"
    mkdir logs

    echo "Building Docker containers"
    invoke_docker_compose build

    echo "Setting up SSL certificates"
    invoke_docker_compose up -d proxy
    invoke_docker_compose run --rm  certbot certonly --webroot --webroot-path /var/www/certbot/ -d "$HOST_NAME" -d "www.$HOST_NAME"
    invoke_docker_compose down proxy

    update_config "config/nginx.template"

    invoke_manage update_musicbrainz_data

    invoke_docker_compose up -d
    echo "Initialization complete; server started at $HOST_NAME"
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
    invoke_docker_compose run --rm web sh -c "python3 manage.py loaddata /app/temp_database_file.json && rm /app/temp_database_file.json"
}

check_for_backup_dir() {
    if [ -z "$BACKUP_DIR" ]; then
        echo "failed: missing BACKUP_DIR in env file."
        exit
    fi
    if [ -z "$BACKUP_DAYS_TO_KEEP" ]; then
        echo "failed: missing BACKUP_DAYS_TO_KEEP in env file."
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
    dump_data "$TODAY_DIR/database.json"
    echo
    echo "Copying media files"
    invoke_docker_compose cp web:/app/media "$TODAY_DIR/"
    echo
    DELETE_DATE=$(date --date="${BACKUP_DAYS_TO_KEEP} days ago" +"%F")
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
        open app/htmlcov/index.html
    else
        echo "Don't run coverage/tests in prod."
    fi
}

connect_to_database() {
    invoke_docker_compose exec -e PGPASSWORD="$DATABASE_PASSWORD" db sh -c "psql -U $DATABASE_USER -d $DATABASE_NAME"
}

update_app() {
    git pull
    invoke_docker_compose up --build -d
}

tailwind() {
    # Tailwind's gotta be installed on the system, can't figure out how to dockerize it
    if [ "$IS_DEV" = "True" ]; then
        npx @tailwindcss/cli -i app/findshows/static/findshows/style.css -o app/findshows/static/findshows/tailwind.css --watch
    else
        echo "Only run tailwind in dev"
    fi
}

nightly_tasks() {
    echo
    date -Iseconds
    echo "MOD REMINDER"
    invoke_manage send_mod_reminder
    echo "BACKUP"
    backup
    echo "UPDATING APP"
    update_app
    echo "ROTATING LOGS"
    logrotate config/logrotate.conf
}

weekly_tasks() {
    echo
    date -Iseconds
    echo "SENDING WEEKLY EMAIL"
    invoke_manage send_weekly_recs
}

biweekly_tasks() {
    echo
    date -Iseconds
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
    nightly_tasks >> logs/nightly_tasks.log 2>&1
elif [ "$1" = "weekly-tasks" ]; then
    weekly_tasks >> logs/weekly_tasks.log 2>&1
elif [ "$1" = "biweekly-tasks" ]; then
    biweekly_tasks >> logs/biweekly_tasks.log 2>&1
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
elif [ "$1" = "tailwind" ]; then
    tailwind

else
    echo "Running docker-compose with the given command..."
    invoke_docker_compose "$@"
fi
