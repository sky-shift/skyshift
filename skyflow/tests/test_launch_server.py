import argparse
import multiprocessing
import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, mock_open, patch

import yaml

from api_server import launch_server
from skyflow.globals import API_SERVER_CONFIG_PATH
from skyflow.utils.utils import generate_manager_config
from skyflow.globals import API_SERVER_CONFIG_PATH


class TestLaunchAPIServer(unittest.TestCase):

    @patch('os.urandom', return_value=b'\x00' * 32
           )  # Mocks os.urandom to return a predictable value.
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open, read_data=""
           )  # Mocks file opening, read_data can simulate file content.
    @patch('yaml.safe_load'
           )  # Mocks yaml.safe_load to control its return value.
    def test_generate_manager_config(self, mock_yaml_safe_load, mock_file,
                                     mock_makedirs, mock_urandom):
        """
        Test if the manager configuration file is generated correctly.
        """

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
                '00' * 32,  # Corresponds to the mocked os.urandom output
            },
            "users": [],
        }

        # Mock yaml.safe_load to return the mock_config_dict
        mock_yaml_safe_load.return_value = mock_config_dict

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
    def test_main(self, mock_check_etcd, mock_generate_config, mock_uvicorn):
        """
        Test the main function with mocked dependencies.
        """
        test_host = "127.0.0.1"
        test_port = 8080
        launch_server.main(test_host,
                           test_port,
                           workers=multiprocessing.cpu_count())

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
