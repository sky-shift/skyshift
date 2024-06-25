import json
import os
import tarfile
import tempfile
from unittest.mock import patch, MagicMock

from skyshift.cluster_manager.ray.ray_utils import (
    create_archive,
    copy_file_to_remote,
    process_cluster_status,
    extract_job_name,
    map_ray_status_to_task_status,
    fetch_all_job_statuses,
    copy_required_files,
    get_remote_home_directory,
)
from skyshift.templates.resource_template import ResourceEnum

def test_create_archive():
    """Test creating a tar archive from a directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file_path = os.path.join(temp_dir, "test_file.txt")
        with open(temp_file_path, "w") as temp_file:
            temp_file.write("test content")
        
        archive_name = os.path.join(temp_dir, "test_archive.tar.gz")
        create_archive(temp_dir, archive_name)
        
        assert os.path.exists(archive_name)
        with tarfile.open(archive_name, "r:gz") as tar:
            assert "test_file.txt" in tar.getnames()


def test_copy_file_to_remote():
    """Test copying a file to a remote system."""
    ssh_client = MagicMock()
    local_path = "/local/path/to/file.txt"
    remote_path = "/remote/path/to/file.txt"
    
    with patch("skyshift.cluster_manager.ray.ray_utils.ssh_send_command") as mock_ssh_send_command:
        with patch("paramiko.SSHClient.open_sftp", return_value=MagicMock()) as mock_open_sftp:
            
            copy_file_to_remote(ssh_client, local_path, remote_path)
            
            mock_ssh_send_command.assert_called_once_with(ssh_client, "mkdir -p /remote/path/to")

# 
base_status_dict = {
    "data": {
        "clusterStatus": {
            "loadMetricsReport": {
                "usageByNode": {
                    "node1": {
                        "CPU": [1, 4],
                        "memory": [1024, 2048],
                        "GPU": [0, 1],
                        "objectStoreMemory": [512, 1024]
                    }
                }
            }
        }
    }
}


def test_process_cluster_status_usage():
    """Test processing cluster status to extract resource usage information."""
    status_dict = json.loads(json.dumps(base_status_dict))
    result = process_cluster_status(status_dict, usage=False)
    expected = {
        "node1": {
            ResourceEnum.CPU.value: 4,
            ResourceEnum.MEMORY.value: 2048 / (1024 ** 2),
            ResourceEnum.GPU.value: 1,
            ResourceEnum.DISK.value: 1024 / (1024 ** 2),
        }
    }
    assert result == expected

def test_process_cluster_status_capacity():
    """Test processing cluster status to extract resource capacity information."""
    status_dict = json.loads(json.dumps(base_status_dict))
    result = process_cluster_status(status_dict, usage=True)
    expected = {
        "node1": {
            ResourceEnum.CPU.value: 3,
            ResourceEnum.MEMORY.value: (2048 - 1024) / (1024 ** 2),
            ResourceEnum.GPU.value: 1,
            ResourceEnum.DISK.value: (1024 - 512) / (1024 ** 2),
        }
    }
    assert result == expected

def test_process_cluster_status_empty():
    """Test processing cluster status with empty input."""
    status_dict = {}
    result = process_cluster_status(status_dict, usage=False)
    expected = {}
    assert result == expected

def test_process_cluster_status_missing_resources():
    """Test processing cluster status with missing resources."""
    status_dict = json.loads(json.dumps(base_status_dict))
    status_dict["data"]["clusterStatus"]["loadMetricsReport"]["usageByNode"]["node1"] = {"CPU": [1, 4]}
    result = process_cluster_status(status_dict, usage=True)
    expected = {
        "node1": {
            ResourceEnum.CPU.value: 3 
        }
    }
    assert result == expected

def test_process_cluster_status_multiple_nodes():
    """Test processing cluster status with multiple nodes."""
    status_dict = json.loads(json.dumps(base_status_dict))
    status_dict["data"]["clusterStatus"]["loadMetricsReport"]["usageByNode"]["node2"] = {
        "GPU": [0, 1],
        "objectStoreMemory": [512, 1024]
    }
    result = process_cluster_status(status_dict, usage=False)
    expected = {
        "node1": {
            ResourceEnum.CPU.value: 4,
            ResourceEnum.MEMORY.value: 2048 / (1024 ** 2),
            ResourceEnum.GPU.value: 1,
            ResourceEnum.DISK.value: 1024 / (1024 ** 2)
        },
        "node2": {
            ResourceEnum.GPU.value: 1,
            ResourceEnum.DISK.value: 1024 / (1024 ** 2)
        }
    }
    assert result == expected

def test_process_cluster_status_mixed_gpu_types():
    """Test processing cluster status with mixed GPU types."""
    status_dict = json.loads(json.dumps(base_status_dict))
    status_dict["data"]["clusterStatus"]["loadMetricsReport"]["usageByNode"]["node1"]["accelerator_type:NVIDIA_TESLA_K80"] = [0, 2]
    result = process_cluster_status(status_dict, usage=False)
    expected = {
        "node1": {
            ResourceEnum.CPU.value: 4,
            ResourceEnum.MEMORY.value: 2048 / (1024 ** 2),
            ResourceEnum.GPU.value: 1,
            ResourceEnum.DISK.value: 1024 / (1024 ** 2),
            "NVIDIA_TESLA_K80": 2
        }
    }
    assert result == expected

def test_extract_job_name():
    """Test extracting the original job name from the submission ID."""
    submission_id = "job-name-1234-5678"
    job_name = extract_job_name(submission_id)
    assert job_name == "job-name"


def test_map_ray_status_to_task_status():
    """Test mapping Ray job statuses to SkyShift's statuses."""
    ray_status = "SUCCEEDED"
    task_status = map_ray_status_to_task_status(ray_status)
    assert task_status == "COMPLETED"


def test_fetch_all_job_statuses_same_name():
    """Test processing the status of all jobs with the same name from the Ray cluster."""
    job_details = [
        MagicMock(submission_id="job-1-1234", job_id="job-1-1234", status="RUNNING"),
        MagicMock(submission_id="job-2-5678", job_id="job-2-5678", status="SUCCEEDED")
    ]
    result = fetch_all_job_statuses(job_details)
    expected = {
        "tasks": {
            "job": {"job-1-1234": "RUNNING", "job-2-5678": "COMPLETED"}
        },
        "containers": {
            "job": {"job-1-1234": "RUNNING", "job-2-5678": "COMPLETED"}
        }
    }
    assert json.dumps(result, sort_keys=True) == json.dumps(expected, sort_keys=True)

def test_fetch_all_job_statuses_different_names():
    """Test processing the status of all jobs with different names from the Ray cluster."""
    job_details = [
        MagicMock(submission_id="job1-1-1234", job_id="job1-1-1234", status="RUNNING"),
        MagicMock(submission_id="job2-2-5678", job_id="job2-2-5678", status="SUCCEEDED")
    ]
    result = fetch_all_job_statuses(job_details)
    expected = {
        "tasks": {
            "job1": {"job1-1-1234": "RUNNING"},
            "job2": {"job2-2-5678": "COMPLETED"}
        },
        "containers": {
            "job1": {"job1-1-1234": "RUNNING"},
            "job2": {"job2-2-5678": "COMPLETED"}
        }
    }
    assert json.dumps(result, sort_keys=True) == json.dumps(expected, sort_keys=True)

def test_fetch_all_job_statuses_invalid_submission_ids():
    """Test processing the status of jobs with invalid submission IDs."""
    job_details = [
        MagicMock(submission_id="invalid-1234", job_id="job-1-1234", status="RUNNING"),
        MagicMock(submission_id="job2-2-5678", job_id="job2-5678", status="SUCCEEDED")
    ]
    result = fetch_all_job_statuses(job_details)
    expected = {
        "tasks": {
            "job2": {"job2-5678": "COMPLETED"}
        },
        "containers": {
            "job2": {"job2-5678": "COMPLETED"}
        }
    }
    assert json.dumps(result, sort_keys=True) == json.dumps(expected, sort_keys=True)

def test_fetch_all_job_statuses_missing_job_ids():
    """Test processing the status of jobs with missing job IDs."""
    job_details = [
        MagicMock(submission_id="job-1-1234", job_id=None, status="RUNNING"),
        MagicMock(submission_id="job-2-5678", job_id="job-2-5678", status="SUCCEEDED")
    ]
    result = fetch_all_job_statuses(job_details)
    expected = {
        "tasks": {
            "job": {"job-2-5678": "COMPLETED"}
        },
        "containers": {
            "job": {"job-2-5678": "COMPLETED"}
        }
    }
    assert json.dumps(result, sort_keys=True) == json.dumps(expected, sort_keys=True)

def test_fetch_all_job_statuses_mixed_valid_invalid():
    """Test processing mixed valid and invalid job details."""
    job_details = [
        MagicMock(submission_id="job1-1-1234", job_id="job1-1-1234", status="RUNNING"),
        MagicMock(submission_id="invalid-1234", job_id="invalid-1234", status="FAILED"),
        MagicMock(submission_id="job2-2-5678", job_id="job2-2-5678", status="SUCCEEDED"),
        MagicMock(submission_id=None, job_id="job3-3-9012", status="PENDING")
    ]
    result = fetch_all_job_statuses(job_details)
    expected = {
        "tasks": {
            "job1": {"job1-1-1234": "RUNNING"},
            "job2": {"job2-2-5678": "COMPLETED"}
        },
        "containers": {
            "job1": {"job1-1-1234": "RUNNING"},
            "job2": {"job2-2-5678": "COMPLETED"}
        }
    }
    assert json.dumps(result, sort_keys=True) == json.dumps(expected, sort_keys=True)

def test_copy_required_files():
    """Test copying required files to the remote system."""
    ssh_client = MagicMock()
    logger = MagicMock()
    remote_dir = "/remote/dir"
    
    with patch("skyshift.cluster_manager.ray.ray_utils.create_archive") as mock_create_archive:
        with patch("skyshift.cluster_manager.ray.ray_utils.copy_file_to_remote") as mock_copy_file_to_remote:
            with patch("skyshift.cluster_manager.ray.ray_utils.extract_archive_on_remote") as mock_extract_archive_on_remote:
                with patch("skyshift.cluster_manager.ray.ray_utils.os.remove") as mock_os_remove:
                    copy_required_files(ssh_client, remote_dir, logger)
                    
                    mock_create_archive.assert_called_once()
                    mock_copy_file_to_remote.assert_called_once()
                    mock_extract_archive_on_remote.assert_called_once()
                    mock_os_remove.assert_called_once()


def test_get_remote_home_directory():
    """Test fetching the home directory of the remote user."""
    ssh_client = MagicMock()
    
    with patch("skyshift.cluster_manager.ray.ray_utils.ssh_send_command") as mock_ssh_send_command:
        mock_ssh_send_command.return_value = ("/home/user", None)
        home_dir = get_remote_home_directory(ssh_client)
        
        assert home_dir == "/home/user"
