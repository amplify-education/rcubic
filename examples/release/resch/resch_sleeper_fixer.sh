#!/bin/bash
#PRODUCT: release
#SDEP:
#HDEP: release_start.sh

source ../helper/common.sh

sleep 15
rm 'badFile'
rescheduleScript.py --port $4 --addr localhost --script resch_fail.sh $5
exit 0
