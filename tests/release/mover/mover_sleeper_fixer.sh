#!/bin/bash
#PRODUCT: release
#SDEP:
#HDEP: release_start.sh

source ../helper/common.sh

sleep 10
rm 'badFile'
manualOverride.py --port $4 --addr localhost --script mover_fail.sh $5
exit 0
