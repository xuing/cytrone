#!/bin/bash

###########################################################
# Stop the CyTrONE framework
###########################################################

###########################################################
# Usage information

# $ ./stop_cytrone.sh


###########################################################
# Load configuration

: CROND_PREFIX=${CROND_PREFIX:=/home/ubuntu}
CYTRONE_SCRIPTS_CONFIG=$CROND_PREFIX/cytrone/scripts/CONFIG
if [ -f $CYTRONE_SCRIPTS_CONFIG ]; then
        . $CYTRONE_SCRIPTS_CONFIG
fi

echo "# Stop CyTrONE server modules."


###########################################################
# Stop CyTrONE

# Stop the internal server modules by finding the exact process
# This is safer than a broad pkill

echo "* Stop the training server."
PGREP_TRNG=$(pgrep -f "python3 -u ${CODE_DIR}/trngsrv.py")
if [ -n "$PGREP_TRNG" ]; then
    kill $PGREP_TRNG
fi

echo "* Stop the instantiation server."
PGREP_INST=$(pgrep -f "python3 -u ${CODE_DIR}/instsrv.py")
if [ -n "$PGREP_INST" ]; then
    kill $PGREP_INST
fi

echo "* Stop the content server."
PGREP_CONT=$(pgrep -f "python3 -u ${CODE_DIR}/contsrv.py")
if [ -n "$PGREP_CONT" ]; then
    kill $PGREP_CONT
fi

exit 0
