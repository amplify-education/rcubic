#!/bin/bash
#PRODUCT: release
#SDEP:
#HDEP: release_start.sh

source ../helper/common.sh
name=$(basename $0)
time=$[ ( $RANDOM % 30) + 1]
for (( c=1; c<=$time; c++ )); do
    progress=$(( c*100/time))
    sleep 1
    updateProgress.py --port $4 --addr localhost --script $name --progress $progress --version $1 $5
done
exit
