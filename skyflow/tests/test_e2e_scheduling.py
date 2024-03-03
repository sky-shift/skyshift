"""
E2E tests for the scheduling.  Each individual test is not idempotent
but the test suite is idempotent.

Prerequisites : 
    KIND (https://kind.sigs.k8s.io)
    DOCKER
    KUBECTL

Run : pytest test_scheduling.py
"""
import os
import pytest
import subprocess
import tempfile
import time

from click.testing import CliRunner

from skyflow.cli.cli import cli
import skyflow.tests.tests_utils as tests_utils

LAUNCH_SCRIPT_REL_PATH = "../../launch_skyflow.sh"


def _setup_kind_clusters():
    assert tests_utils.create_cluster("test-cluster-1") is True
    assert tests_utils.create_cluster("test-cluster-2") is True


def _breakdown_kind_clusters():
    tests_utils.delete_cluster("test-cluster-1")
    tests_utils.delete_cluster("test-cluster-2")


def _setup_sky_manager(num_workers: int = 1):
    current_file_path = os.path.abspath(__file__)
    current_directory = os.path.dirname(current_file_path)

    install_script_path = os.path.abspath(
        os.path.join(current_directory, LAUNCH_SCRIPT_REL_PATH))

    workers_param_str = str(num_workers)
    command = ["bash", install_script_path, "--workers", workers_param_str]
    print(f"Setup up sky manager command:'{command}'.")

    process = subprocess.Popen(command)
    time.sleep(15)  # Wait for the server to start
    return process


def _breakdown_sky_manager():
    current_file_path = os.path.abspath(__file__)
    current_directory = os.path.dirname(current_file_path)
    install_script_path = os.path.abspath(
        os.path.join(current_directory, LAUNCH_SCRIPT_REL_PATH))

    command = ["bash", install_script_path, "--kill"]
    print(f"Sky manager cleaned up ({command}).")
    process = subprocess.Popen(command)
    time.sleep(15)  # Wait for the server to stop

    # Additional cleanup for pristine env.
    home_dir = os.environ.get('HOME')

    etcd_dir = f'{home_dir}/.etcd'
    command = ["rm", "-rf", etcd_dir]
    print(f"Etcd directory cleaned up ({command}).")

    subprocess.Popen(command)

    sky_dir = f'{home_dir}/.sky'
    command = ["rm", "-rf", sky_dir]
    print(f"Sky working directory cleaned up ({command}).")
    subprocess.Popen(command)

    skyconf_dir = f'{home_dir}/.skyconf'
    command = ["rm", "-rf", skyconf_dir]
    print(f"Sky config working directory cleaned up ({command}).")
    subprocess.Popen(command)

    return process


@pytest.fixture(scope="session", autouse=True)
def setup_and_shutdown():
    with tempfile.TemporaryDirectory() as temp_data_dir:
        # Kill any running sky_manager processes
        _breakdown_sky_manager()
        print("Sky manager clean up complete.")

        # Clean up from previous test
        _breakdown_kind_clusters()
        print("Kind clusters clean up complete.")

        # Setup clusters to use for testing
        _setup_kind_clusters()
        print("Kind clusters setup complete.")
        # @TODO(dmatch01) Remove sleep after #191 issue is resolved
        time.sleep(30)

        # Setup and run Sky Manager
        process = _setup_sky_manager()

        print(
            "Setup up sky manager and kind clusters completed.  Testing begins..."
        )

        yield  # Test execution happens here

        print("Test clean up begins.")

        # Kill any running sky_manager processes
        _breakdown_sky_manager()
        print("Cleaned up sky manager and API Server.")

        # Cleanup kind clusters after test
        _breakdown_kind_clusters()
        print("Cleaned up kind clusters.")

        # Stop ETCD server (launch script does not cleanup etcd. Putting etcd cleanup here.)
        subprocess.run('pkill -9 -f "etcd"', shell=True)  # pylint: disable=subprocess-run-check
        print("Cleaned up ETCD.")


@pytest.fixture
def runner():
    return CliRunner()


def test_filter_with_match_label(runner):
    # Construct the command with parameters
    cluster_1_name = "kind-test-cluster-1"
    cluster_2_name = "kind-test-cluster-2"
    manager = "k8"

    cmd = ['get', 'clusters']
    result = runner.invoke(cli, cmd)
    print(f'get cluster results\n{result.output}')
    assert result.exit_code == 0

    # Delete existing cluster 1 without labels in Sky Manager
    print(f'Deleting cluster {cluster_1_name}.')
    cmd = ['delete', 'cluster', cluster_1_name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert cluster_1_name in result.output

    # Define cluster 1 labels
    labels = [("sky-cluster-id", cluster_1_name), ("purpose", "dev")]
    label_args = []
    for key, value in labels:
        label_args.extend(['--labels', f'{key}', f'{value}'])

    # Re-create cluster 1 in Sky Manager
    print("Re-creating cluster cluster.")
    cmd = ['create', 'cluster', cluster_1_name, '--manager', manager
           ] + label_args
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert cluster_1_name in result.output

    print(
        "Waiting for 10 seconds before getting re-added cluster with labels.")
    # @TODO(dmatch01): Change sleep to code for cluster ready with timeout
    time.sleep(10)  # Wait for the server to start

    cmd = ['get', 'cluster', cluster_1_name]
    result = runner.invoke(cli, cmd)
    print(f'get cluster results\n{result.output}')
    assert result.exit_code == 0
    assert cluster_1_name in result.output

    # Delete existing cluster 2 without labels in Sky Manager
    print(f'Deleting cluster {cluster_2_name}.')
    cmd = ['delete', 'cluster', cluster_2_name]
    result = runner.invoke(cli, cmd)
    print(f'Delete cluster {cluster_2_name} results\n{result.output}')
    assert result.exit_code == 0

    # Define cluster 2 labels
    labels = [("sky-cluster-id", cluster_2_name), ("purpose", "staging")]
    label_args = []
    for key, value in labels:
        label_args.extend(['--labels', f'{key}', f'{value}'])

    # Re-create cluster 2 in Sky Manager
    print("Re-creating cluster 2.")
    cmd = ['create', 'cluster', cluster_2_name, '--manager', manager
           ] + label_args
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert cluster_2_name in result.output

    print(
        "Waiting for 15 seconds before getting re-added cluster with labels.")
    # @TODO(dmatch01): Change sleep to code for cluster ready with timeout
    time.sleep(15)  # Wait for the server to start

    cmd = ['get', 'cluster', cluster_2_name]
    result = runner.invoke(cli, cmd)
    print(f'get cluster results\n{result.output}')
    assert result.exit_code == 0
    assert cluster_2_name in result.output

    # Deploy unschedulable workload
    current_file_path = os.path.abspath(__file__)
    current_directory = os.path.dirname(current_file_path)
    relative_path_to_prod_yaml = "../../examples/batch_job_with_prod_filter_single_match_label.yaml"
    yaml_file_path = os.path.abspath(
        os.path.join(current_directory, relative_path_to_prod_yaml))

    print('Deploying unschedulable cluster filtering workload')
    cmd = ['apply', '-f', yaml_file_path]
    result = runner.invoke(cli, cmd)
    print(f'get cluster results\n{result.output}')
    assert result.exit_code == 0, f'Job creation failed: {yaml_file_path}'

    print("Waiting for 15 seconds to allow for job to get deployed.")
    # @TODO(dmatch01): Change sleep to code for job running with timeout
    time.sleep(15)  # Wait for the job to start

    batch_job_name = "my-batch-job-with-prod-filter-match-label"
    cmd = ['get', 'job', batch_job_name]
    result = runner.invoke(cli, cmd)
    print(f'get job\n{result.output}')
    assert result.exit_code == 0
    assert batch_job_name in result.output
    assert cluster_1_name not in result.output
    assert cluster_2_name not in result.output

    # Delete unschedulable workload
    cmd = ['delete', 'job', batch_job_name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0, f'Job deletion failed: {yaml_file_path}'

    # Deploy schedulable workload
    relative_path_to_dev_yaml = "../../examples/batch_job_with_dev_filter_single_match_label.yaml"
    yaml_file_path = os.path.abspath(
        os.path.join(current_directory, relative_path_to_dev_yaml))

    print('Deploying schedulable filtering workload')
    cmd = ['apply', '-f', yaml_file_path]
    result = runner.invoke(cli, cmd)
    print(f'get cluster results\n{result.output}')
    assert result.exit_code == 0, f'Job creation failed: {yaml_file_path}'

    print("Waiting for 15 seconds to allow for job to get deployed.")
    # @TODO(dmatch01): Change sleep to code for job running with timeout
    time.sleep(15)  # Wait for the server to start

    batch_job_name = "my-batch-job-with-dev-filter-match-label"
    cmd = ['get', 'job', batch_job_name]
    result = runner.invoke(cli, cmd)
    print(f'get job\n{result.output}')
    assert result.exit_code == 0
    assert batch_job_name in result.output
    assert cluster_1_name in result.output

    # Delete deployed job
    print('Deleting schedulable filtering workload')
    cmd = ['delete', 'job', batch_job_name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0, f'Job deletion failed: {yaml_file_path}'


def test_filter_with_match_expression(runner):
    # Construct the command with parameters
    cluster_1_name = "kind-test-cluster-1"
    cluster_2_name = "kind-test-cluster-2"
    manager = "k8"

    cmd = ['get', 'clusters']
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0

    cmd = ['get', 'cluster', cluster_1_name]
    result = runner.invoke(cli, cmd)
    print(f'get cluster results\n{result.output}')
    assert result.exit_code == 0
    assert cluster_1_name in result.output

    cmd = ['get', 'cluster', cluster_2_name]
    result = runner.invoke(cli, cmd)
    print(f'get cluster results\n{result.output}')
    assert result.exit_code == 0
    assert cluster_2_name in result.output

    # Deploy unschedulable workload
    current_file_path = os.path.abspath(__file__)
    current_directory = os.path.dirname(current_file_path)
    relative_path_to_prod_yaml = "../../examples/batch_job_with_prod_filter_single_match_expression.yaml"
    yaml_file_path = os.path.abspath(
        os.path.join(current_directory, relative_path_to_prod_yaml))

    print('Deploying unschedulable cluster filtering workload')
    cmd = ['apply', '-f', yaml_file_path]
    result = runner.invoke(cli, cmd)
    print(f'get cluster results\n{result.output}')
    assert result.exit_code == 0, f'Job creation failed: {yaml_file_path}'

    print("Waiting for 15 seconds to allow for job to get deployed.")
    # @TODO(dmatch01): Change sleep to code for job running with timeout
    time.sleep(15)  # Wait for the job to start

    batch_job_name = "my-batch-job-with-prod-filter-match-expression"
    cmd = ['get', 'job', batch_job_name]
    result = runner.invoke(cli, cmd)
    print(f'get job\n{result.output}')
    assert result.exit_code == 0
    assert batch_job_name in result.output
    assert cluster_1_name not in result.output
    assert cluster_2_name not in result.output

    # Delete unschedulable workload
    cmd = ['delete', 'job', batch_job_name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0, f'Job deletion failed: {yaml_file_path}'

    # Deploy schedulable workload
    relative_path_to_dev_yaml = "../../examples/batch_job_with_dev_filter_single_match_expression.yaml"
    yaml_file_path = os.path.abspath(
        os.path.join(current_directory, relative_path_to_dev_yaml))

    print('Deploying schedulable cluster filtering workload')
    cmd = ['apply', '-f', yaml_file_path]
    result = runner.invoke(cli, cmd)
    print(f'get cluster results\n{result.output}')
    assert result.exit_code == 0, f'Job creation failed: {yaml_file_path}'

    print("Waiting for 15 seconds to allow for job to get deployed.")
    # @TODO(dmatch01): Change sleep to code for job running with timeout
    time.sleep(15)  # Wait for the job to start

    batch_job_name = "my-batch-job-with-dev-filter-match-expression"
    cmd = ['get', 'job', batch_job_name]
    result = runner.invoke(cli, cmd)
    print(f'get job\n{result.output}')
    assert result.exit_code == 0
    assert batch_job_name in result.output
    assert cluster_1_name in result.output

    # Delete deployed job
    print('Deleting schedulable filtering workload')
    cmd = ['delete', 'job', batch_job_name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0, f'Job deletion failed: {yaml_file_path}'


def test_preference(runner):
    # Construct the command with parameters
    cluster_1_name = "kind-test-cluster-1"
    cluster_2_name = "kind-test-cluster-2"
    manager = "k8"

    # Deploy preferred dev cluster workload
    current_file_path = os.path.abspath(__file__)
    current_directory = os.path.dirname(current_file_path)
    relative_path_to_dev_yaml = "../../examples/batch_job_with_dev_preference.yaml"
    yaml_file_path = os.path.abspath(
        os.path.join(current_directory, relative_path_to_dev_yaml))

    print('Deploying workload with dev preferences.')
    cmd = ['apply', '-f', yaml_file_path]
    result = runner.invoke(cli, cmd)
    print(f'apply results\n{result.output}')
    assert result.exit_code == 0, f'Job creation failed: {yaml_file_path}'

    print("Waiting for 15 seconds to allow for job to get deployed.")
    # @TODO(dmatch01): Change sleep to code for job running with timeout
    time.sleep(15)  # Wait for the job to start

    batch_job_name = "mybatchjobwithdevpreference"
    cmd = ['get', 'job', batch_job_name]
    result = runner.invoke(cli, cmd)
    print(f'get job\n{result.output}')
    assert result.exit_code == 0
    assert batch_job_name in result.output
    assert cluster_1_name in result.output

    # Delete dev cluster preference workload
    cmd = ['delete', 'job', batch_job_name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0

    # Deploy preferred staging cluster workload
    relative_path_to_dev_yaml = "../../examples/batch_job_with_staging_preference.yaml"
    yaml_file_path = os.path.abspath(
        os.path.join(current_directory, relative_path_to_dev_yaml))

    print('Deploying workload with staging preferences.')
    cmd = ['apply', '-f', yaml_file_path]
    result = runner.invoke(cli, cmd)
    print(f'apply job results\n{result.output}')
    assert result.exit_code == 0, f'Job creation failed: {yaml_file_path}'

    print("Waiting for 15 seconds to allow for job to get deployed.")
    # @TODO(dmatch01): Change sleep to code for job running with timeout
    time.sleep(15)  # Wait for the job to start

    batch_job_name = "mybatchjobwithstagingpreference"
    cmd = ['get', 'job', batch_job_name]
    result = runner.invoke(cli, cmd)
    print(f'get job\n{result.output}')
    assert result.exit_code == 0
    assert batch_job_name in result.output
    assert cluster_2_name in result.output
