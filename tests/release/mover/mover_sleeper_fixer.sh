#!/bin/bash
#PRODUCT: release
#SDEP:
#HDEP: release_start.sh

source ../helper/common.sh

sleep 15
rm 'badFile'
manualOverride.py --port 31337 --addr localhost --token 123 --script mover_fail.sh
exit 0
