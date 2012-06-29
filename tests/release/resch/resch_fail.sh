#!/bin/bash
#PRODUCT: release
#SDEP:
#HDEP: resch_touch_file.sh

source ../helper/common.sh

if [ -f 'badFile' ]; then
    exit 1
fi
exit 0
