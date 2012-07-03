#!/bin/bash
#PRODUCT: release
#SDEP:
#HDEP: release_start.sh

source ../helper/common.sh
name=$(basename $(readlink -nf $0))
time=$[ ( $RANDOM % 30) + 1]
for (( c=1; c<=$time; c++ )); do
    progress=$(( c*100/time))
    sleep 1
    updateProgress.py --port 31337 --addr localhost --token 123 --script $name --progress $progress --version mc0.2.7_rc1
done
exit
