"""
    Tests for CLI interface. Mostly integration tests with the API server and ETCD.

    To test, run:
    pytest skyflow/tests/cli_tests.py

    and for running a specific test:
    pytest skyflow/tests/cli_tests.py::test_create_cluster_success
"""
import multiprocessing
import os
import shutil
import subprocess
import tempfile
import time

import pytest
from click.testing import CliRunner

from skyflow.cli.cli import cli


@pytest.fixture(scope="session", autouse=True)
def etcd_backup_and_restore():
    with tempfile.TemporaryDirectory() as temp_data_dir:
        # Kill any running sky_manager processes
        subprocess.run("pkill -f launch_sky_manager", shell=True)  # pylint: disable=subprocess-run-check

        print("Using temporary data directory for ETCD:", temp_data_dir)
        workers = 1
        data_directory = temp_data_dir
        current_file_path = os.path.abspath(__file__)
        current_directory = os.path.dirname(current_file_path)
        relative_path_to_script = "../../api_server/launch_server.py"
        install_script_path = os.path.abspath(
            os.path.join(current_directory, relative_path_to_script))

        data_directory = temp_data_dir
        command = [
            "python", install_script_path, "--workers",
            str(workers), "--data-directory", data_directory
        ]

        process = subprocess.Popen(command)
        time.sleep(15)  # Wait for the server to start

        yield  # Test execution happens here

        # Stop the application and ETCD server
        process.terminate()
        process.wait()
        subprocess.run('pkill -f etcd', shell=True)  # pylint: disable=subprocess-run-check

        print("Cleaned up temporary ETCD data directory.")


@pytest.fixture
def runner():
    return CliRunner()


# ==============================================================================
# Cluster tests


def test_create_cluster_success(runner):
    name = "valid-cluster"
    manager = "k8"
    cmd = ['create', 'cluster', name, '--manager', manager]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert name in result.output


@pytest.mark.parametrize(
    "name,manager",
    [
        ("", "k8"),  # Empty name
    ])
def test_create_cluster_invalid_input(runner, name, manager):
    cmd = ['create', 'cluster', name, '--manager', manager]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0


def test_create_cluster_duplicate_name(runner):
    name = "duplicate-cluster"
    manager = "k8"
    # First attempt
    cmd = ['create', 'cluster', name, '--manager', manager]
    result_first = runner.invoke(cli, cmd)
    assert result_first.exit_code == 0  # Assuming success on the first attempt
    # Second attempt with the same name
    result_second = runner.invoke(cli, cmd)
    assert result_second.exit_code != 0
    assert "already exists" in result_second.output


def test_create_cluster_unsupported_manager(runner):
    name = "invalid-manager-cluster"
    manager = "unsupported_manager"
    cmd = ['create', 'cluster', name, '--manager', manager]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "Unsupported manager_type" in result.output


def test_get_specific_cluster(runner, name='valid-cluster'):
    cmd = ['get', 'cluster', name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert name in result.output


def test_get_specific_cluster_not_valid(runner, name=''):
    cmd = ['get', 'cluster', name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0


def test_get_all_clusters(runner):
    cmd = ['get', 'cluster']
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert "valid-cluster" in result.output


def test_get_nonexistent_cluster(runner, name='nonexistent-cluster'):
    cmd = ['get', 'cluster', name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "not found" in result.output


def test_delete_cluster_success(runner, name="valid-cluster"):
    cmd = ['delete', 'cluster', name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    result = runner.invoke(cli, ['get', 'cluster', name])
    assert result.exit_code != 0
    result = runner.invoke(cli, ['get', 'cluster'])
    assert result.exit_code == 0
    assert name not in result.output
    result = runner.invoke(cli, ['delete', 'cluster', name])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_create_cluster_success_no_manager(runner):
    name = "cluster1"
    manager = "k8"
    cmd = ['create', 'cluster', name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert name in result.output
    name = "cluster2"
    manager = "k8"
    cmd = ['create', 'cluster', name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert name in result.output


# ==============================================================================
# Job tests


def test_create_job_success(runner):

    # Define the job specifications
    job_spec = {
        "name": "valid-job",
        "namespace": "default",
        "image": "gcr.io/sky-burst/skyburst:latest",
        "cpus": 1.0,
        "memory": 512.0,
        "run": "echo Hello World",
    }

    # Define job labels
    labels = [("labelkey1", "value1"), ("labellkey2", "value2")]
    label_args = []
    for key, value in labels:
        label_args.extend(['--labels', f'{key}', f'{value}'])

    # Construct the command with parameters
    cmd = [
        'create', 'job', job_spec["name"], '--namespace', job_spec["namespace"]
    ] + label_args + [
        '--image', job_spec["image"], '--cpus',
        str(job_spec["cpus"]), '--memory',
        str(job_spec["memory"]), '--run', job_spec["run"]
    ]

    # Execute the command
    result = runner.invoke(cli, cmd)
    print(result.output)
    assert result.exit_code == 0, "Job creation failed"


def test_create_job_invalid_image(runner):
    name = "invalid-image-job"
    image = "invalid-image-format-#"

    cmd = ['create', 'job', name, '--image', image]

    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "Invalid image format" in result.output


def test_create_job_invalid_resources(runner):
    name = "invalid-resources-job"
    cpus = -1
    memory = -512

    cmd = ['create', 'job', name, '--cpus', str(cpus), '--memory', str(memory)]

    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "Invalid resource" in result.output


def test_create_job_unsupported_restart_policy(runner):
    name = "unsupported-restart-policy-job"
    restart_policy = "UnsupportedPolicy"

    cmd = ['create', 'job', name, '--restart_policy', restart_policy]

    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "Invalid restart policy" in result.output


def test_create_job_duplicate_labels_envs(runner):
    name = "duplicate-labels-envs-job"
    labels = [("key", "value"), ("key", "value2")]
    envs = [("ENV_VAR", "value"), ("ENV_VAR", "value2")]

    cmd = [
        'create', 'job', name, '--labels',
        *[':'.join(label) for label in labels], '--envs',
        *[':'.join(env) for env in envs]
    ]

    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "Invalid label" in result.output or "Duplicate envs" in result.output


def test_get_specific_job(runner, name='valid-job', namespace='default'):
    cmd = ['get', 'job', name, '--namespace', namespace]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert name in result.output


def test_get_all_jobs_in_namespace(runner, namespace='default'):
    cmd = ['get', 'job', '--namespace', namespace]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert "valid-job" in result.output


def test_get_job_nonexistent_namespace(runner,
                                       name='some-job',
                                       namespace='nonexistent-namespace'):
    cmd = ['get', 'job', name, '--namespace', namespace]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "not found" in result.output


def test_get_nonexistent_job(runner,
                             name='nonexistent-job',
                             namespace='default'):
    cmd = ['get', 'job', name, '--namespace', namespace]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "not found" in result.output


def test_delete_job_nonexistent_namespace(runner,
                                          name="some-job",
                                          namespace="nonexistent-namespace"):
    cmd = ['delete', 'job', name, '--namespace', namespace]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "not exist" in result.output


def test_delete_job_success(runner, name="valid-job", namespace="default"):
    cmd = ['delete', 'job', name, '--namespace', namespace]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert name in result.output


def test_delete_nonexistent_job(runner,
                                name="nonexistent-job",
                                namespace="default"):
    cmd = ['delete', 'job', name, '--namespace', namespace]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "not exist" in result.output


def test_delete_job_repeatedly(runner, name="valid-job", namespace="default"):
    # Assuming the job was deleted before
    cmd = ['delete', 'job', name, '--namespace', namespace]
    result_first = runner.invoke(cli, cmd)
    assert result_first.exit_code != 0
    assert "not exist" in result_first.output


# ==============================================================================
# Namespace tests


def test_create_namespace_success(runner):
    name = "valid-namespace"
    cmd = ['create', 'namespace', name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0


@pytest.mark.parametrize(
    "name",
    [
        "!!!invalid",  # Invalid characters
        "",  # Empty name
        "a" * 256,  # Exceeding length limit.
    ])
def test_create_namespace_invalid_name(runner, name):
    cmd = ['create', 'namespace', name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "is invalid" in result.output


def test_create_duplicate_namespace(runner):
    name = "unique-namespace"
    runner.invoke(cli, ['create', 'namespace', name])
    # Attempt to create again with the same name
    result_duplicate = runner.invoke(cli, ['create', 'namespace', name])
    assert result_duplicate.exit_code != 0
    assert "already exists" in result_duplicate.output


def test_get_specific_namespace(runner):
    name = "valid-namespace"
    cmd = ['get', 'namespace', name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert name in result.output


def test_get_all_namespaces(runner):
    cmd = ['get', 'namespace']
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert "valid-namespace" in result.output


def test_delete_namespace_success(runner):
    name = "valid-namespace"
    cmd = ['delete', 'namespace', name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert name in result.output
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_delete_nonexistent_namespace(runner):
    name = "nonexistent-namespace"
    cmd = ['delete', 'namespace', name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "does not exist" in result.output


# ==============================================================================
# FilterPolicy tests
@pytest.mark.parametrize(
    "name, namespace, labelselector, includecluster, excludecluster", [
        ('test-policy-4', 'default', [('app', 'test')], ['cluster1'
                                                         ], ['cluster2']),
    ])
def test_create_filter_policy_success(runner, name, namespace, labelselector,
                                      includecluster, excludecluster):
    label_args = []
    for key, value in labelselector:
        label_args.extend(['--labelSelector', f'{key}', f'{value}'])

    include_args = ['--includeCluster={}'.format(cl) for cl in includecluster]
    exclude_args = ['--excludeCluster={}'.format(cl) for cl in excludecluster]

    cmd = ['create', 'filterPolicy', name, '--namespace', namespace
           ] + label_args + include_args + exclude_args

    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0, f"Unexpected output: {result.output}"


@pytest.mark.parametrize("missing_arg", [
    ([
        'create', 'filterPolicy', '--namespace', 'default', '--labelSelector',
        'app', 'test'
    ]),
    ([
        'create', 'filterPolicy', 'nonexistent-cluster', '--includeCluster',
        'fake', '--excludeCluster', 'cluster1'
    ]),
    ([
        'create', 'filterPolicy', 'nonexistent-v2-cluster', '--includeCluster',
        'cluster2', '--excludeCluster', 'faker'
    ]),
    ([
        'create', 'filterPolicy', '%$·"!Q', '--namespace', 'default',
        '--labelSelector', 'invalid'
    ]),
    ([
        'create', 'filterPolicy', 'conflicting-clusters', '--namespace',
        'default', '--includeCluster', 'cluster1', '--excludeCluster',
        'cluster1'
    ]),
    ([
        'create', 'filterPolicy', '%$·"!Q', '--namespace', '%$·"!Q',
        '--labelSelector', 'app', 'test'
    ]),
])
def test_create_filter_policy_missing_required_params(runner, missing_arg):
    result = runner.invoke(cli, missing_arg)
    print(missing_arg)
    assert result.exit_code != 0
    assert "Missing" in result.output or "Invalid" in result.output or "not found" in result.output or "requires 2 arguments" in result.output


def test_create_filter_policy_idempotent(runner):
    name = "not-idempotent-policy"
    cmd = ['create', 'filterPolicy', name]
    result_first = runner.invoke(cli, cmd)
    result_second = runner.invoke(cli, cmd)
    assert result_first.exit_code == 0
    assert result_second.exit_code != 0
    assert "already exists" in result_second.output


def test_get_specific_filter_policy(runner,
                                    name='test-policy-4',
                                    namespace='default'):
    cmd = ['get', 'filterPolicy', name, '--namespace', namespace]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert name in result.output
    assert namespace in result.output


def test_get_all_filter_policies_in_namespace(runner, namespace='default'):
    cmd = ['get', 'filterPolicy', '--namespace', namespace]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert "test-policy-4" in result.output


def test_get_nonexistent_filter_policy(runner,
                                       name='nonexistent-policy',
                                       namespace='default'):
    cmd = ['get', 'filterPolicy', name, '--namespace', namespace]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "not found" in result.output


def test_delete_nonexistent_filter_policy(runner,
                                          name="nonexistent-policy",
                                          namespace="default"):
    cmd = ['delete', 'filterPolicy', name, '--namespace', namespace]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "not exist" in result.output


def test_delete_filter_policy_incorrect_namespace(
        runner, name="test-policy-4", namespace="incorrect-namespace"):
    cmd = ['delete', 'filterPolicy', name, '--namespace', namespace]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "not exist" in result.output


def test_delete_filter_policy_repeatedly(runner,
                                         name="test-policy-4",
                                         namespace="default"):
    # First deletion attempt
    cmd = ['delete', 'filterPolicy', name, '--namespace', namespace]
    result_first = runner.invoke(cli, cmd)
    assert result_first.exit_code == 0

    # Second deletion attempt for the same policy
    result_second = runner.invoke(cli, cmd)
    assert result_second.exit_code != 0
    assert "not exist" in result_second.output

    # Attempt to fetch the deleted policy
    get_cmd = ['get', 'filterPolicy', name, '--namespace', namespace]
    get_result = runner.invoke(cli, get_cmd)
    assert get_result.exit_code != 0
    assert "not found" in get_result.output


# ==============================================================================
# Link tests


def test_create_link_success(runner):
    name = "valid-link"
    source = "cluster1"
    target = "cluster2"
    cmd = ['create', 'link', name, '--source', source, '--target', target]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert name in result.output


def test_create_link_with_duplicate_names(runner):
    name = "duplicate-name-link"
    cmd_first = [
        'create', 'link', name, '--source', 'cluster1', '--target', 'cluster2'
    ]
    cmd_second = [
        'create', 'link', name, '--source', 'cluster2', '--target', 'cluster1'
    ]

    result_first = runner.invoke(cli, cmd_first)
    result_second = runner.invoke(cli, cmd_second)

    assert result_first.exit_code == 0, "First link creation should succeed"
    assert "Created link" in result_first.output
    assert result_second.exit_code != 0, "Duplicate link name should cause failure"
    assert "already exists" in result_second.output


@pytest.mark.parametrize("source, target", [
    ("nonexistent-cluster1", "cluster2"),
    ("cluster1", "nonexistent-cluster2"),
    ("nonexistent-cluster1", "nonexistent-cluster2"),
    (None, "cluster2"),
    ("", "cluster2"),
    ("cluster1", None),
    ("cluster1", ""),
])
def test_create_link_nonexistent_clusters(runner, source, target):
    name = "invalid-link"
    cmd = ['create', 'link', name, '--source', source, '--target', target]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "not found" in result.output or "Invalid" in result.output or "Missing option" in result.output


@pytest.mark.parametrize("name", [
    " ",
    "!",
])
def test_create_link_with_invalid_names(runner, name):
    cmd = [
        'create', 'link', name, '--source', 'cluster1', '--target', 'cluster2'
    ]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "is invalid" in result.output


def test_create_link_missing_source_or_target(runner):
    name = "link-missing-details"
    cmd_without_source = ['create', 'link', name, '--target', 'cluster2']
    cmd_without_target = ['create', 'link', name, '--source', 'cluster1']

    result_without_source = runner.invoke(cli, cmd_without_source)
    result_without_target = runner.invoke(cli, cmd_without_target)

    assert result_without_source.exit_code != 0, "Missing source should cause failure"
    assert result_without_target.exit_code != 0, "Missing target should cause failure"
    assert "Missing" in result_without_source.output
    assert "Missing" in result_without_target.output


def test_create_link_same_source_target(runner):
    name = "self-link"
    cluster = "cluster1"
    cmd = ['create', 'link', name, '--source', cluster, '--target', cluster]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "cannot be the same" in result.output


def test_get_specific_link(runner, name='valid-link'):
    cmd = ['get', 'link', name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert name in result.output
    assert "INIT" in result.output


def test_get_all_links(runner):
    cmd = ['get', 'link']
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0


def test_delete_link_success(runner, name="valid-link"):
    cmd = ['delete', 'link', name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert f"Deleted link {name}." in result.output


def test_delete_nonexistent_link(runner, name="nonexistent-link"):
    cmd = ['delete', 'link', name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "not exist" in result.output


# ==============================================================================
# Service tests


def test_create_minimal_service(runner):
    name = "valid-service-minimal"
    cmd = ['create', 'service', name]

    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert name in result.output


def test_create_service_success(runner):
    name = "valid-service"
    namespace = "default"
    service_type = "ClusterIP"
    selector = ['app', 'myapp']
    ports = [80, 8080]
    cluster = "cluster1"

    cmd = [
        'create', 'service', name, '--namespace', namespace, '--service_type',
        service_type, '--selector', selector[0], selector[1], '--ports',
        ports[0], ports[1], '--cluster', cluster
    ]

    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert name in result.output


def test_create_service_unsupported_type(runner):
    name = "unsupported-type-service"
    service_type = "UnsupportedType"

    cmd = ['create', 'service', name, '--service_type', service_type]

    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "not supported" in result.output


@pytest.mark.parametrize("ports", [[-1, 8080], [80, 70000]])
def test_create_service_invalid_ports(runner, ports):
    name = "invalid-ports-service"

    cmd = ['create', 'service', name, '--ports', ports[0], ports[1]]

    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "out of valid range" in result.output


def test_create_service_invalid_selector(runner):
    name = "invalid-selector-service"
    selector = ["invalid key", "value"]
    cmd = ['create', 'service', name, '--selector', selector[0], selector[1]]

    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "Invalid value: Selector" in result.output


def test_create_service_invalid_namespace(runner):
    name = "valid-service"
    namespace = "!!!invalid"
    service_type = "ClusterIP"
    selector = ['app', 'myapp']
    ports = [80, 8080]
    cluster = "cluster1"

    cmd = [
        'create', 'service', name, '--namespace', namespace, '--service_type',
        service_type, '--selector', selector[0], selector[1], '--ports',
        ports[0], ports[1], '--cluster', cluster
    ]

    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "is invalid" in result.output


@pytest.mark.parametrize("selector", [['', 'myapp'], ['app', '']])
def test_create_service_empty_selector(runner, selector):
    name = "empty-selector-service"
    service_type = "ClusterIP"
    ports = [80, 8080]
    cluster = "cluster1"

    cmd = [
        'create', 'service', name, '--service_type', service_type,
        '--selector', selector[0], selector[1], '--ports', ports[0], ports[1],
        '--cluster', cluster
    ]

    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "Invalid value: Selector" in result.output


def test_create_service_duplicate_selector_keys(runner):
    name = "duplicate-selector-keys-service"
    service_type = "ClusterIP"
    # Simulating duplicate selector keys by repeating the selector option
    selector = ['app', 'myapp', 'app', 'anotherapp']
    ports = [80, 8080]
    cluster = "cluster1"

    cmd = [
        'create', 'service', name, '--service_type', service_type,
        '--selector', *selector, '--ports', ports[0], ports[1], '--cluster',
        cluster
    ]

    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "unexpected extra arguments" in result.output


def test_create_service_nonexistent_cluster(runner):
    name = "service-nonexistent-cluster"
    cluster = "nonexistent-cluster"

    cmd = ['create', 'service', name, '--cluster', cluster]

    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "not found" in result.output


def test_get_specific_service(runner):
    name = "valid-service"
    namespace = "default"
    cmd = ['get', 'service', name, '--namespace', namespace]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0


def test_get_all_services_in_namespace(runner):
    namespace = "default"
    cmd = ['get', 'service', '--namespace', namespace]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert "valid-service" in result.output


def test_delete_service_success(runner):
    name = "valid-service"
    cmd = ['delete', 'service', name]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert name in result.output
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_delete_nonexistent_service(runner):
    name = "nonexistent-service"
    namespace = "default"
    cmd = ['delete', 'service', name, '--namespace', namespace]
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0
    assert "does not exist" in result.output


# ==============================================================================
# Endpoints tests


def test_create_endpoints_success(runner):
    result = runner.invoke(cli, [
        'create', 'edps', 'valid-endpoints', '--namespace', 'default',
        '--num_endpoints', '3', '--exposed', '--primary_cluster', 'cluster1',
        '--selector', 'app', 'myapp'
    ])
    assert result.exit_code == 0
    assert 'valid-endpoints' in result.output


def test_create_endpoints_success_minimal(runner):
    name = "valid-endpoints-minimal"
    result = runner.invoke(cli, ['create', 'edps', name])
    assert result.exit_code == 0
    assert name in result.output


@pytest.mark.parametrize("num_endpoints", [0, 1, 100])
def test_create_endpoints_various_numbers(runner, num_endpoints):
    result = runner.invoke(cli, [
        'create', 'edps', f'endpoints-{num_endpoints}', '--namespace',
        'default', '--num_endpoints',
        str(num_endpoints), '--primary_cluster', 'cluster1'
    ])
    assert result.exit_code == 0
    assert f'endpoints-{num_endpoints}' in result.output


def test_create_endpoints_invalid_namespace(runner):
    result = runner.invoke(cli, [
        'create', 'edps', 'invalid-namespace-endpoints', '--namespace',
        '!!!invalid', '--primary_cluster', 'cluster1'
    ])
    assert result.exit_code != 0
    assert "Invalid namespace name" in result.output


def test_create_endpoints_negative_number(runner):
    result = runner.invoke(cli, [
        'create', 'edps', 'negative-endpoints', '--namespace', 'default',
        '--num_endpoints', '-1', '--primary_cluster', 'cluster1'
    ])
    assert result.exit_code != 0
    assert "must be non-negative" in result.output


def test_create_endpoints_invalid_selector(runner):
    result = runner.invoke(
        cli,
        [
            'create',
            'edps',
            'invalid-selector',
            '--namespace',
            'default',
            '--selector',
            'invalid',  # Missing value
            '--primary_cluster',
            'cluster1'
        ])
    assert result.exit_code != 0
    assert "Got unexpected extra argument" in result.output


def test_create_endpoints_exposed_without_primary(runner):
    result = runner.invoke(
        cli,
        [
            'create',
            'edps',
            'exposed-no-primary',
            '--namespace',
            'default',
            '--exposed',
            # No --primary_cluster specified
        ])
    assert result.exit_code == 0


def test_create_endpoints_invalid_cluster(runner):
    result = runner.invoke(cli, [
        'create', 'edps', 'invalid-selector', '--namespace', 'default',
        '--primary_cluster', 'fake-cluster'
    ])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_get_specific_endpoints(runner):
    name = "valid-endpoints"
    namespace = "default"
    result = runner.invoke(
        cli, ['get', 'endpoints', name, '--namespace', namespace])
    assert result.exit_code == 0
    assert name in result.output


def test_get_all_endpoints_in_namespace(runner):
    namespace = "default"
    result = runner.invoke(cli, ['get', 'endpoints', '--namespace', namespace])
    assert result.exit_code == 0
    assert "valid-endpoints" in result.output


def test_delete_endpoints_success(runner):
    name = "valid-endpoints"
    namespace = "default"
    result = runner.invoke(cli, ['delete', 'endpoints', name])
    assert result.exit_code == 0
    result = runner.invoke(
        cli, ['delete', 'endpoints', name, '--namespace', namespace])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_delete_nonexistent_endpoints(runner):
    name = "nonexistent-service"
    namespace = "default"
    result = runner.invoke(
        cli, ['delete', 'endpoints', name, '--namespace', namespace])
    assert result.exit_code != 0
    assert "does not exist" in result.output
