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
import shutil
import subprocess
import tempfile
import time

import pytest
import yaml
from click.testing import CliRunner

import skyshift.tests.tests_utils as tests_utils
from skyshift.cli.cli import cli

LAUNCH_SCRIPT_REL_PATH = "../../launch_skyshift.sh"


def _setup_kind_clusters():
    """Setup KIND clusters."""

    assert tests_utils.create_cluster("test-cluster-1") is True
    assert tests_utils.create_cluster("test-cluster-2") is True


def _breakdown_kind_clusters():
    """Teardown KIND clusters."""

    tests_utils.delete_cluster("test-cluster-1")
    tests_utils.delete_cluster("test-cluster-2")


def _setup_sky_manager(num_workers: int = 16):
    """Setup Sky Manager."""

    current_file_path = os.path.abspath(__file__)
    current_directory = os.path.dirname(current_file_path)

    install_script_path = os.path.abspath(
        os.path.join(current_directory, LAUNCH_SCRIPT_REL_PATH))

    workers_param_str = str(num_workers)
    command = ["bash", install_script_path, "--workers", workers_param_str]
    print(f"Setup up sky manager command:'{command}'.")

    subprocess.run(command, check=True)


def _breakdown_sky_manager():
    """Teardown Sky Manager."""

    current_file_path = os.path.abspath(__file__)
    current_directory = os.path.dirname(current_file_path)
    install_script_path = os.path.abspath(
        os.path.join(current_directory, LAUNCH_SCRIPT_REL_PATH))

    command = ["bash", install_script_path, "--kill"]
    print(f"Sky manager cleaned up ({command}).")
    subprocess.run(command, check=True)

    def delete_dir_if_exists(dir_path):
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            shutil.rmtree(dir_path)
            print(f"Cleaned up {dir_path}.")

    # Additional cleanup for pristine env.
    for dir_path in ["~/.etcd", "~/.skyconf"]:
        delete_dir_if_exists(os.path.expanduser(dir_path))


def _load_batch_job():
    """Load a batch job from the example folder."""

    current_file_path = os.path.abspath(__file__)
    current_directory = os.path.dirname(current_file_path)
    # Load yaml file
    relative_path_to_prod_yaml = "../../examples/batch_job.yaml"
    yaml_file_path = os.path.abspath(
        os.path.join(current_directory, relative_path_to_prod_yaml))
    # Load
    with open(yaml_file_path, 'r') as file:
        job_dict = yaml.safe_load(file)
    return job_dict


@pytest.fixture(scope="session", autouse=True)
def setup_and_shutdown():
    """Setup/teardown a fresh environment."""

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
    _setup_sky_manager()

    time.sleep(30)

    print(
        "Setup up sky manager and kind clusters completed.  Testing begins...")

    yield  # Test execution happens here

    print("Test clean up begins.")

    # Kill any running sky_manager processes
    _breakdown_sky_manager()
    print("Cleaned up sky manager and API Server.")

    # Cleanup kind clusters after test
    _breakdown_kind_clusters()
    print("Cleaned up kind clusters.")

    # Stop ETCD server (launch script does not cleanup etcd. Putting etcd cleanup here.)
    subprocess.run('pkill -9 -f "etcd"', shell=True, check=False)
    print("Cleaned up ETCD.")


@pytest.fixture(name="runner")
def fixture_runner():
    """The CLI runner."""
    return CliRunner()


def deploy(runner, job_dict):
    """Deploy the given `job_dict`."""
    with tempfile.NamedTemporaryFile('w') as temp_file:
        yaml.dump(job_dict, temp_file)
        cmd = ['apply', '-f', temp_file.name]
        result = runner.invoke(cli, cmd)
        print(f'get cluster results\n{result.output}')
        assert result.exit_code == 0, f"Job creation failed: {job_dict['metadata']['name']}"


# pylint: disable=R0915 (too-many-statements)
def test_filter_with_match_label(runner):
    """Test the placement filter with match label."""

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

    print("Waiting for 5 seconds before creating cluster with labels.")
    time.sleep(5)

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
        "Waiting for 15 seconds before getting re-added cluster with labels.")
    # @TODO(dmatch01): Change sleep to code for cluster ready with timeout
    time.sleep(15)  # Wait for the server to start

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

    # Deploy unschedulable workload. There are two clusters with purpose: staging, dev.
    # The job is configured to run on clusters with purpose: prod.
    job_dict = _load_batch_job()

    batch_job_name = "my-batch-job-with-prod-filter-match-label"
    job_dict['metadata']['name'] = batch_job_name
    job_dict['spec']['placement'] = {
        'filters': [{
            'name': 'filter-1',
            'match_labels': {
                'purpose': 'prod'
            }
        }]
    }

    # create temporary file
    print('Deploying unschedulable cluster filtering workload')
    deploy(runner, job_dict)

    print(
        f"Waiting for 10 seconds to allow for job {batch_job_name} to get deployed."
    )
    # @TODO(dmatch01): Change sleep to code for job running with timeout
    time.sleep(10)  # Wait for the job to start

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
    assert result.exit_code == 0, f'Job deletion failed: {batch_job_name}'

    batch_job_name = "my-batch-job-with-dev-filter-match-label"
    job_dict['metadata']['name'] = batch_job_name
    job_dict['spec']['placement'] = {
        'filters': [{
            'name': 'filter-1',
            'match_labels': {
                'purpose': 'dev'
            }
        }]
    }

    # Deploy schedulable workload
    print('Deploying schedulable filtering workload')
    deploy(runner, job_dict)

    print(
        f"Waiting for 10 seconds to allow for job {batch_job_name} to get deployed."
    )
    # @TODO(dmatch01): Change sleep to code for job running with timeout
    time.sleep(10)  # Wait for the server to start

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
    assert result.exit_code == 0, f'Job deletion failed: {batch_job_name}'


# pylint: disable=R0915 (too-many-statements)
def test_filter_with_match_expression(runner):
    """Test the placement filter with match expression."""

    # Construct the command with parameters
    cluster_1_name = "kind-test-cluster-1"
    cluster_2_name = "kind-test-cluster-2"

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

    job_dict = _load_batch_job()

    # Deploy unschedulable workload
    batch_job_name = "my-batch-job-with-prod-filter-match-expression"
    job_dict['metadata']['name'] = batch_job_name
    job_dict['spec']['placement'] = {
        'filters': [{
            'name':
            'filter-1',
            'match_expressions': [{
                'key': 'purpose',
                'operator': 'In',
                'values': ['demo', 'prod', 'exclusive']
            }]
        }]
    }

    print('Deploying unschedulable cluster filtering workload')
    deploy(runner, job_dict)

    print("Waiting for 15 seconds to allow for job to get deployed.")
    # @TODO(dmatch01): Change sleep to code for job running with timeout
    time.sleep(15)  # Wait for the job to start

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
    assert result.exit_code == 0, f'Job deletion failed: {batch_job_name}'

    # Deploy schedulable workload
    batch_job_name = "my-batch-job-with-dev-filter-match-expression"
    job_dict['metadata']['name'] = batch_job_name
    job_dict['spec']['placement'] = {
        'filters': [{
            'name':
            'filter-1',
            'match_expressions': [{
                'key':
                'purpose',
                'operator':
                'In',
                'values': ['demo', 'prod', 'dev', 'exclusive']
            }]
        }]
    }

    print('Deploying schedulable cluster filtering workload')
    deploy(runner, job_dict)

    print("Waiting for 15 seconds to allow for job to get deployed.")
    # @TODO(dmatch01): Change sleep to code for job running with timeout
    time.sleep(15)  # Wait for the job to start

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
    assert result.exit_code == 0, f'Job deletion failed: {batch_job_name}'


def test_preference(runner):
    """Test the placement preference scheduling."""

    # Construct the command with parameters
    cluster_1_name = "kind-test-cluster-1"
    cluster_2_name = "kind-test-cluster-2"

    job_dict = _load_batch_job()

    # Launch job with priority/preference for dev cluster.
    batch_job_name = "my-batch-job-with-dev-preference"
    job_dict['metadata']['name'] = batch_job_name
    job_dict['spec']['placement'] = {
        'preferences': [{
            'name': 'updated-preference-1',
            'match_labels': {
                'purpose': 'dev'
            },
            'weight': 100
        }, {
            'name': 'updated-preference-2',
            'match_labels': {
                'purpose': 'staging'
            },
            'weight': 2
        }]
    }

    print('Deploying workload with dev preferences.')
    deploy(runner, job_dict)

    print("Waiting for 15 seconds to allow for job to get deployed.")
    # @TODO(dmatch01): Change sleep to code for job running with timeout
    time.sleep(15)  # Wait for the job to start

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

    # Launch job with priority for dev cluster.
    batch_job_name = "my-batch-job-with-staging-preference"
    job_dict['metadata']['name'] = batch_job_name
    job_dict['spec']['placement'] = {
        'preferences': [{
            'name': 'updated-preference-1',
            'match_labels': {
                'purpose': 'staging'
            },
            'weight': 100
        }, {
            'name': 'updated-preference-2',
            'match_labels': {
                'purpose': 'dev'
            },
            'weight': 2
        }]
    }

    print('Deploying workload with staging preferences.')
    deploy(runner, job_dict)

    print("Waiting for 15 seconds to allow for job to get deployed.")
    # @TODO(dmatch01): Change sleep to code for job running with timeout
    time.sleep(15)  # Wait for the job to start

    cmd = ['get', 'job', batch_job_name]
    result = runner.invoke(cli, cmd)
    print(f'get job\n{result.output}')
    assert result.exit_code == 0
    assert batch_job_name in result.output
    assert cluster_2_name in result.output
