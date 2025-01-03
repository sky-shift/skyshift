"""
Test launching the API server.
"""

import multiprocessing
import os
import sys
import unittest
from unittest.mock import mock_open, patch

import yaml

from api_server import launch_server
from skyshift.globals import API_SERVER_CONFIG_PATH
from skyshift.utils.utils import generate_manager_config


class TestLaunchAPIServer(unittest.TestCase):
    """Test launching the API server."""

    # Mocks os.urandom to return a predictable value.
    @patch('os.urandom')
    @patch('os.makedirs')
    # Mocks file opening, read_data can simulate file content.
    @patch('builtins.open', new_callable=mock_open, read_data="")
    def test_generate_manager_config(self, mock_file, mock_makedirs,
                                     mock_urandom):
        """
        Test if the manager configuration file is generated correctly.
        """
        mock_urandom.side_effect = lambda len: b'\x00' * len

        # Remove the API_SERVER_CONFIG_PATH file if it exists
        if os.path.exists(os.path.expanduser(API_SERVER_CONFIG_PATH)):
            os.remove(os.path.expanduser(API_SERVER_CONFIG_PATH))

        test_host = "127.0.0.1"
        test_port = 8080
        mock_config_dict = {
            "api_server": {
                "host": test_host,
                "port": test_port,
                "secret":
                '00' * 256,  # Corresponds to the mocked os.urandom output
            },
            "users": [],
            "contexts": [],
            "current_context": "",
        }

        # Call the function with test data
        generate_manager_config(test_host, test_port)

        # Expected configuration dictionary with a mocked 'secret'
        expected_config = mock_config_dict  # Or construct this as needed

        # Build the expected absolute file path
        expected_file_path = os.path.expanduser(API_SERVER_CONFIG_PATH)

        # Verify if the directories were created
        mock_makedirs.assert_called_with(os.path.dirname(expected_file_path),
                                         exist_ok=True)

        # Verify if the file was opened correctly
        mock_file.assert_called_with(expected_file_path, "w")

        # Verify if the correct content was written to the file
        written_content = "".join(
            [call.args[0] for call in mock_file().write.call_args_list])
        self.assertEqual(yaml.safe_load(written_content), expected_config)

    @patch('api_server.launch_server.uvicorn.run')
    @patch('api_server.launch_server.generate_manager_config')
    @patch('api_server.launch_server.check_and_install_etcd')
    # pylint: disable=R0201 (no-self-use)
    def test_main(self, mock_check_etcd, mock_generate_config, mock_uvicorn):
        """
        Test the main function with mocked dependencies.
        """
        test_host = "127.0.0.1"
        test_port = 8080
        launch_server.main(test_host,
                           test_port,
                           workers=multiprocessing.cpu_count(),
                           reset=False)

        mock_check_etcd.assert_called_once()
        mock_generate_config.assert_called_with(test_host, test_port)
        mock_uvicorn.assert_called_with("api_server:app",
                                        host=test_host,
                                        port=test_port,
                                        workers=multiprocessing.cpu_count())

    def test_parse_args(self):
        """
        Test the parse_args function for correct argument parsing.
        """
        test_args = [
            'script_name', '--host', '127.0.0.1', '--port', '8080',
            '--workers', '4'
        ]
        with patch.object(sys, 'argv', test_args):
            args = launch_server.parse_args()
            self.assertEqual(args.host, '127.0.0.1')
            self.assertEqual(args.port, 8080)
            self.assertEqual(args.workers, 4)


if __name__ == '__main__':
    unittest.main()
