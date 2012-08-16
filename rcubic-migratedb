#!/bin/bash

# Migrates db version and sets up extra githead column
# and creates dv version table

if [ $# -ne 1 ]; then
    echo "Expected one argument: db path"
    exit 1
fi
sqlite3 $1 "ALTER TABLE latest_events add column githead text;"
sqlite3 $1 "ALTER TABLE events add column githead text;"
sqlite3 $1 "CREATE TABLE rcubic_db_support(db_version text unique);"
sqlite3 $1 "INSERT INTO rcubic_db_support VALUES('1.0');"
