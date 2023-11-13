import argparse
import multiprocessing

import uvicorn

from sky_manager.utils.utils import generate_manager_config

API_SERVER_HOST = 'localhost'
API_SERVER_PORT = 50051

if __name__ == '__main__':
    # Create the parser
    parser = argparse.ArgumentParser(description="Launch API Service for Sky Manager.")

    # Add arguments
    parser.add_argument("--host", type=str, default=API_SERVER_HOST,
                        help="Host for the API server (default: %(default)s)")
    parser.add_argument("--port", type=int, default=API_SERVER_PORT,
                        help="Port for the API server (default: %(default)s)")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="Run the server in dry-run mode (default: False)")
    # Parse the arguments
    args = parser.parse_args()
    uvicorn.run('sky_manager.api_server.api_server:app', host=args.host, port=args.port, workers=multiprocessing.cpu_count())
    generate_manager_config(args.host, args.port)