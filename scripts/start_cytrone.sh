#!/bin/bash

###########################################################
# Start the CyTrONE framework
###########################################################

###########################################################
# Usage information

# $ ./start_cytrone.sh


###########################################################
# Load configuration

# Prepare logger
trap 'logger -p daemon.warning receive SIGHUP' HUP

# Read configuration
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

echo "# Start CyTrONE server modules sequentially."

# Start the internal CyTrONE modules (servers listening for commands)
# Start content and instantiation servers first as they are dependencies for the training server.

echo "* Start content server on       ${CONTENT_HOST} (port ${CONTENT_PORT})."
export PYTHONPATH=${PYTHONPATH}:/home/ubuntu/cytrone/cylms
cd ${CODE_DIR}; python3 -u ${CODE_DIR}/contsrv.py --path ${CYLMS_PATH} --config ${CYLMS_CONFIG} &
sleep 2

echo "* Start instantiation server on ${INSTANTIATION_HOST} (port ${INSTANTIATION_PORT})."
cd ${CODE_DIR}; python3 -u ${CODE_DIR}/instsrv.py --path ${CYRIS_PATH} --cyprom ${CYPROM_PATH} &
sleep 2

echo "* Start training server on      ${TRAINING_HOST} (port ${TRAINING_PORT})."
cd ${CODE_DIR}; python3 -u ${CODE_DIR}/trngsrv.py &
sleep 2

echo "# All services started."

exit 0