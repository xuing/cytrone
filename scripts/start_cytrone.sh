#!/bin/bash

###########################################################
# Start the CyTrONE framework (Manual contsrv.py launch)
###########################################################

###########################################################
# Load configuration

: CROND_PREFIX=${CROND_PREFIX:=/home/ubuntu}
CYTRONE_SCRIPTS_CONFIG=$CROND_PREFIX/cytrone/scripts/CONFIG

if [ -f $CYTRONE_SCRIPTS_CONFIG ]; then
	. $CYTRONE_SCRIPTS_CONFIG
fi

# Set local variables
LOG=$LOGDIR/cytrone-`date +%Y%m%dT%H%M`.log

# Switch logfile path
exec < /dev/null >> $LOG 2>&1


###########################################################
# Start CyTrONE

echo "# Starting remaining CyTrONE server modules."
echo "# IMPORTANT: This script assumes you have started contsrv.py manually in a separate terminal."

# Start the internal CyTrONE modules (servers listening for commands)

echo "* Start instantiation server on ${INSTANTIATION_HOST} (port ${INSTANTIATION_PORT})."
cd ${CODE_DIR}; python3 -u ${CODE_DIR}/instsrv.py --path ${CYRIS_PATH} --cyprom ${CYPROM_PATH} &
sleep 2

echo "* Start training server on      ${TRAINING_HOST} (port ${TRAINING_PORT})."
cd ${CODE_DIR}; python3 -u ${CODE_DIR}/trngsrv.py &
sleep 2

echo "# All services started."

exit 0