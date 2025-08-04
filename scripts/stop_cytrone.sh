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

# Stop the internal server modules
echo "* Stop the training server."
pkill -f trngsrv.py

echo "* Stop the instantiation server."
pkill -f instsrv.py

echo "* Stop the content server."
pkill -f contsrv.py

exit 0