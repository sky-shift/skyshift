#!/bin/bash
# Automatic script to launch Skyflow's API server and controller manager.
#
# Usage:
#    # Launch Skyflow with desired # of workers and logging behavior.
#    bash launch_skyflow.sh --workers <num_workers> --log <file|stdout|none>
#    # Kill Skyflow processes.
#    bash launch_skyflow.sh --kill

# Default arguments
workers=$(nproc)
log="stdout" # Default logging to stdout for both programs

# Function to parse command-line arguments
parse_args() {
  while [[ "$#" -gt 0 ]]; do
    case $1 in
      -k|--kill) kill_flag=1 ;;
      -w|--workers) workers="$2"; shift ;;
      -l|--log) log="$2"; shift ;;
      *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
  done
}

# Function to launch programs with logging options
launch_skyflow() {
  cd "$(dirname "$0")"
  
  # Determine logging behavior and construct command
  case $log in
    file)
      api_log_cmd="python api_server/launch_server.py --workers $workers > api_server.log 2>&1"
      sky_manager_log_cmd="python skyflow/launch_sky_manager.py > sky_manager.log 2>&1"
      ;;
    stdout)
      api_log_cmd="python api_server/launch_server.py --workers $workers"
      sky_manager_log_cmd="python skyflow/launch_sky_manager.py"
      ;;
    none)
      api_log_cmd="python api_server/launch_server.py --workers $workers > /dev/null 2>&1"
      sky_manager_log_cmd="python skyflow/launch_sky_manager.py > /dev/null 2>&1"
      ;;
  esac
  
  # Execute commands with specified logging
  eval $api_log_cmd &
  # Sleep for two seconds for API server to fully boot up
  sleep 2
  eval $sky_manager_log_cmd &
}

# Function to kill programs and ensure they are terminated
terminate_skyflow() {
  echo "Terminating Skyflow processes..."
  # Get PID of server
  pkill -f launch_sky_manager.py
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
    pkill -f launch_server.py
    pkill -9 -f "multiprocessing.spawn"
    pkill -f launch_sky_manager.py
    sleep 1
  done

  echo "Skyflow processes terminated successfully."
}

# Parse the command-line arguments
parse_args "$@"

if [[ "$kill_flag" -eq 1 ]]; then
  # Kill the programs if the kill flag is set
  terminate_skyflow
else
  # Launch the programs otherwise
  launch_skyflow
fi
