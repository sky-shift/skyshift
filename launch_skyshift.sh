#!/bin/bash
# Automatic script to launch SkyShift's API server and controller manager.
#
# Usage:
#    # Launch SkyShift with desired # of workers and logging behavior.
#    bash launch_skyshift.sh --workers <num_workers> --log <file|stdout|none>
#    # Kill SkyShift API server and controller manager.
#    bash launch_skyshift.sh --kill

# Default arguments
workers=$(nproc)
log="stdout" # Default logging to stdout for both programs
api_log_file="api_server.log"
manager_log_file="sky_manager.log"

# Function to parse command-line arguments
parse_args() {
  while [[ "$#" -gt 0 ]]; do
    case $1 in
      -k|--kill) kill_flag=1 ;;
      -w|--workers) workers="$2"; shift ;;
      -l|--log) log="$2"; shift ;;
      --api-log-file) api_log_file="$2"; shift ;;
      --manager-log-file) manager_log_file="$2"; shift ;;
      *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
  done
}

# Function to check if programs are already running
is_running() {
  if pgrep -f "$1" >/dev/null; then
    echo "$1 is already running."
    return 0
  fi
  return 1
}

# Function to launch programs with logging options
# Function to launch programs with logging options
launch_skyshift() {
  cd "$(dirname "$0")"

  # Determine logging behavior and construct command for API server
  if ! is_running "launch_server.py"; then
    case $log in
      file)
        api_log_cmd="python api_server/launch_server.py --workers $workers > $api_log_file 2>&1"
        ;;
      stdout)
        api_log_cmd="python api_server/launch_server.py --workers $workers"
        ;;
      none)
        api_log_cmd="python api_server/launch_server.py --workers $workers > /dev/null 2>&1"
        ;;
    esac
    eval $api_log_cmd &
    echo "API Server launched."
    # Sleep for five seconds for API server to fully boot up
    sleep 5
  fi

  # Determine logging behavior and construct command for Sky Manager
  if ! is_running "launch_sky_manager.py"; then
    case $log in
      file)
        sky_manager_log_cmd="python skyshift/launch_sky_manager.py > $manager_log_file 2>&1"
        ;;
      stdout)
        sky_manager_log_cmd="python skyshift/launch_sky_manager.py"
        ;;
      none)
        sky_manager_log_cmd="python skyshift/launch_sky_manager.py > /dev/null 2>&1"
        ;;
    esac
    eval $sky_manager_log_cmd &
    echo "Sky Manager launched."
  fi
}

# Function to kill programs and ensure they are terminated
terminate_skyshift() {
  echo "Terminating SkyShift processes..."
  # Get PID of server
  pkill -9 -f "launch_sky_manager.py"
  server_pid=$(pgrep -f launch_server.py)
  if [[ -z $server_pid ]]; then
    echo "API server not running."
  else
    kill -9 $server_pid
    # Kill FastAPI/Uvicorn zombie worker processes.
    pkill -9 -f "multiprocessing.spawn"
  fi
  sleep 2 # Give some time for processes to terminate gracefully

  # While these processes exist, kill them.
  while pgrep -f launch_server.py || pgrep -f launch_sky_manager.py; do
    pkill -9 -f launch_server.py
    pkill -9 -f "multiprocessing.spawn"
    pkill -9 -f launch_sky_manager.py
    sleep 1
  done

  echo "SkyShift processes terminated successfully."
}

# Parse the command-line arguments
parse_args "$@"

if [[ "$kill_flag" -eq 1 ]]; then
  # Kill the programs if the kill flag is set
  terminate_skyshift
else
  # Launch the programs otherwise
  launch_skyshift
fi
