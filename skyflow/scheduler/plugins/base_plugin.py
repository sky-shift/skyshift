"""Specifies the base scheduler plugin class for the SchedulerController."""
import enum
from typing import Dict, List, Tuple, Union

from skyflow.templates import Cluster, Job


class StatusCode(enum.Enum):
    """Represents the return codes for a plugin's methods."""
    SUCCESS = "Success"
    UNSCHEDULABLE = "Unschedulable"
    ERROR = "Error"

class PluginStatus:
    """Represents the status of a plugin.

    PluginStatus indicates the result of running a plugin. It consists of a code, a
    message. An empty PluginStatus is considered successful.
    """
    def __init__(self, code: StatusCode, message: Union[str, List[str]]):
        if code is None:
            self.code: StatusCode = StatusCode.SUCCESS
        else:
            self.code= code
        self.message = message

    def is_successful(self) -> bool:
        """Returns True if the status is successful."""
        return self.code == StatusCode.SUCCESS

    def is_unschedulable(self) -> bool:
        """Returns True if the status is unschedulable."""
        return self.code == StatusCode.UNSCHEDULABLE

    def is_error(self) -> bool:
        """Returns True if the status is an error."""
        return self.code == StatusCode.ERROR


# Inspired from Kubernetes Scheduler Plugin.
class BasePlugin:
    """Represents the template class for any scheduling plugin."""
    def filter(self, cluster: Cluster, job: Job) -> PluginStatus: # pylint: disable=unused-argument, no-self-use
        """Filters the nodes based on the job's resource requirements."""
        return PluginStatus(code=StatusCode.ERROR, message="Filtering not implemented.")

    def score(self, cluster: Cluster, job: Job) -> Tuple[float, PluginStatus]: # pylint: disable=unused-argument, no-self-use
        """Scores the nodes based on the job's resource requirements.

        This plugin returns a score between 0 and 100. The score is used to rank
        the nodes. A score of 0 means the node is the least preferred node, and a
        score of 100 means the node is the most preferred node.
        """
        return 0, PluginStatus(code=StatusCode.ERROR, message="Score not implemented.")

    def spread(self, clusters: List[Cluster], job: Job) -> Tuple[Dict[str, int], PluginStatus]: # pylint: disable=unused-argument, no-self-use
        """Computes the spread of a job's tasks across clusters.

        Returns the allocated # of tasks that can be scheduled on each cluster.
        """
        return {}, PluginStatus(code=StatusCode.ERROR, message="Spread not implemented.")
