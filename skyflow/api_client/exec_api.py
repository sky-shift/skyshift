"""
Exec API.
"""
import asyncio
import sys
import termios
import tty
from asyncio import Event
from concurrent.futures import ThreadPoolExecutor

import requests
import websockets

from skyflow.api_client.object_api import NamespaceObjectAPI
from skyflow.globals import DEFAULT_NAMESPACE


class ExecAPI(NamespaceObjectAPI):
    """
    Exec API for initiating exec connections with apiserver.
    """

    def __init__(self, namespace: str = DEFAULT_NAMESPACE):
        """
        Initializes the ExecAPI with a namespace and sets the object type to 'exec'.
        """
        super().__init__(namespace=namespace, object_type="exec")

    def _build_uri(self, config: dict):
        """
        Builds the WebSocket URI for the exec API based on the provided configuration.

        Args:
            config (Dict[str, Any]): The configuration dictionary containing details needed \
                to build the URI.

        Returns:
            str: The constructed WebSocket URI.
        """

        assert config["spec"]["resource"], "Resource not specified."
        assert config["spec"]["command"], "Command not specified."

        # Construct the URI from the config dict
        quiet = config["spec"]["quiet"]
        resource = config["spec"]["resource"]
        cluster = config["spec"]["cluster"]
        selected_pod = config["spec"]["task"]
        container = config["spec"]["container"]
        command_str = config["spec"][
            "command"]  # Assuming this is already URL-encoded

        # Construct the final URI using the encoded command and other details from the config dict
        return f"{self.url}/{quiet}/{resource}/{cluster}/{selected_pod}/{container}/{command_str}"

    async def _tty_session(self, uri, headers):
        """
        Initiates a TTY session with the Kubernetes API server.

        Args:
            uri (str): The WebSocket URI to connect to.
            headers (Dict[str, str]): The headers to include in the WebSocket request.
        """
        async with websockets.connect(  #pylint: disable=no-member
                uri,
                extra_headers=headers,
                open_timeout=None) as websocket:
            # Prepare terminal for raw mode
            stdin_fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(stdin_fd)
            tty.setraw(stdin_fd)

            input_stop_event = Event()

            async def send_commands():
                loop = asyncio.get_running_loop()
                with ThreadPoolExecutor(1) as executor:
                    try:
                        while not websocket.closed:
                            # Check if input reading should stop
                            if input_stop_event.is_set():
                                break
                            # Use run_in_executor to read without blocking the event loop
                            char = await loop.run_in_executor(
                                executor, sys.stdin.read, 1)
                            if char == '\x04':  # '\x04' is the EOF character
                                break  # Exit the loop to close the connection
                            if not websocket.closed:
                                await websocket.send(char)
                    except (EOFError, KeyboardInterrupt):
                        # Handle end of input or interrupt
                        print("Exiting...")

            async def receive_output():
                try:
                    while True:
                        output = await websocket.recv()
                        sys.stdout.write(output)
                        sys.stdout.flush()
                except websockets.exceptions.ConnectionClosed:
                    input_stop_event.set()  # Signal to stop reading stdin
                except Exception:  # pylint: disable=broad-except
                    input_stop_event.set(
                    )  # Ensure the event is set on any error
                finally:
                    print("Press enter to exit...")

            # Run receiving tasks concurrently with event loop
            receive_task = asyncio.create_task(receive_output())
            send_task = asyncio.create_task(send_commands())

            # Wait for both tasks to complete
            await asyncio.wait([send_task, receive_task],
                               return_when=asyncio.FIRST_COMPLETED)

            # Ensure input_stop_event is set to stop reading from stdin in any case
            input_stop_event.set()
            await websocket.close()

            # Cleanup: restore terminal settings
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)

    def create(self, config: dict):
        """
        Sends a POST request to the API server to create an exec session.

        Args:
            config (Dict[str, Any]): The configuration dictionary for the exec session.

        Returns:
            requests.Response: The response from the API server.
        """
        assert self.namespace, "Method `create` requires a namespace."
        response = requests.post(self._build_uri(config),
                                 json=config,
                                 headers=self.auth_headers)
        return response

    def websocket_stream(self, config: dict):
        """
        Initiates a WebSocket stream for executing commands in a container.

        Args:
            config (Dict[str, Any]): The configuration dictionary for the exec command.
        """
        assert self.namespace, "Method `create` requires a namespace."
        self.url = f"ws://{self.host}:{self.port}/{self.namespace}/{self.object_type}"
        uri = self._build_uri(config)
        headers = self.auth_headers
        asyncio.run(self._tty_session(uri, headers))
