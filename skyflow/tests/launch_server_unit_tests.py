import argparse
import multiprocessing
import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, mock_open, patch

import yaml

from api_server import launch_server


class TestLaunchAPIServer(unittest.TestCase):

    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_manager_config(self, mock_file, mock_makedirs):
        """
        Test if the manager configuration file is generated correctly.
        """
        test_host = "127.0.0.1"
        test_port = 8080

        # Call the function with test data
        launch_server.generate_manager_config(test_host, test_port)

        # Expected configuration dictionary
        expected_config = {
            "api_server": {
                "host": test_host,
                "port": test_port,
            },
        }

        # Build the expected absolute file path
        expected_file_path = os.path.expanduser(
            launch_server.API_SERVER_CONFIG_PATH)

        # Verify if the directories were created
        mock_makedirs.assert_called_with(os.path.dirname(expected_file_path),
                                         exist_ok=True)

        # Verify if the file was opened correctly
        mock_file.assert_called_with(expected_file_path, "w")

        # Verify if the correct content was written to the file
        written_content = "".join(
            [call.args[0] for call in mock_file().write.call_args_list])
        self.assertEqual(yaml.safe_load(written_content), expected_config)

    @patch('subprocess.run')
    @patch('subprocess.Popen')
    def test_check_and_install_etcd(self, mock_popen, mock_run):
        """
        Test the check and installation process of ETCD.
        """
        # Case 1: ETCD is already running
        mock_run.return_value.returncode = 0
        launch_server.check_and_install_etcd()
        mock_run.assert_called_with('ps aux | grep "[e]tcd"',
                                    shell=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True)
        mock_popen.assert_not_called()

        # Case 2: ETCD is not running
        mock_run.return_value.returncode = 1
        mock_popen_inst = MagicMock()
        mock_popen_inst.wait.return_value = 0
        mock_popen_inst.returncode = 0  # Simulate successful installation
        mock_popen.return_value = mock_popen_inst

        launch_server.check_and_install_etcd()
        # Verify that Popen is called with the correct command
        relative_dir = os.path.dirname(os.path.realpath(
            launch_server.__file__))
        mock_popen.assert_called_with(f"{relative_dir}/install_etcd.sh",
                                      shell=True,
                                      start_new_session=True)

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
