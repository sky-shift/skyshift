import json
import sys
from ray.job_submission import JobSubmissionClient

def extract_job_name(submission_id):
    """
    Extracts the original job name from the submission_id.
    """
    parts = submission_id.rsplit('-', 2)
    return '-'.join(parts[:-2]) if len(parts) >= 3 else submission_id

def map_ray_status_to_task_status(ray_status: str) -> str:
    """
    Maps Ray job statuses to Skyflow's statuses.
    """
    status_mapping = {
        "PENDING": "PENDING",
        "RUNNING": "RUNNING",
        "SUCCEEDED": "COMPLETED",
        "FAILED": "FAILED",
        "STOPPED": "DELETED",  # Assuming STOPPED is treated as FAILED
    }
    return status_mapping.get(ray_status, "UNKNOWN")

def fetch_all_job_statuses():
    """
    Fetches the status of all jobs from the Ray cluster.
    """
    client = JobSubmissionClient("http://localhost:8265")  # Assuming this is the Ray dashboard address
    jobs_details = client.list_jobs()  # This fetches all jobs with their details
    
    jobs_dict = {
        "tasks": {},
        "containers": {}
    }
    
    for job in jobs_details:
        job_name = extract_job_name(job.submission_id)
        job_id = job.job_id
        job_status = map_ray_status_to_task_status(job.status)
        
        if job_name not in jobs_dict["tasks"]:
            jobs_dict["tasks"][job_name] = {}
            jobs_dict["containers"][job_name] = {}

        # Assuming all tasks are in the same container for simplicity
        jobs_dict["tasks"][job_name][job_id] = job_status
        jobs_dict["containers"][job_name][job_id] = job_status

    return jobs_dict

def main():
    try:
        job_statuses = fetch_all_job_statuses()
        print(json.dumps(job_statuses))  # Print the job statuses as a JSON string
    except Exception as e:
        print(f"Error fetching job statuses: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
