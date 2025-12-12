#!/bin/bash

curl -v --insecure -H "Content-Type: application/json" -X POST --data "@fg-backup-spec.json" \
    -u "${1}:${2}" "https://${3}/api/mgmt.gateway_backup/1.0/backup"

