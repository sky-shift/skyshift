"""
Link Controller - Manages the dynamic links between clusters. This assumes
that each cluster has the Cluster link/Skupper software/deployment installed.
"""
import queue
import subprocess
import traceback

from skyflow.api_client import ClusterAPI, LinkAPI
from skyflow.cluster_manager.manager_utils import setup_cluster_manager
from skyflow.controllers import Controller
from skyflow.controllers.controller_utils import create_controller_logger
from skyflow.globals import SKYCONF_DIR
from skyflow.network.cluster_linkv2 import create_link, delete_link
from skyflow.structs import Informer
from skyflow.templates import Link, LinkStatusEnum, WatchEventEnum


class LinkController(Controller):
    """
    Link Controller - Manages the dynamic links between clusters. This assumes
    that each cluster has the Cluster link/Skupper software/deployment installed.
    """

    def __init__(self) -> None:
        super().__init__()

        self.logger = create_controller_logger(
            title="[Link Controller]",
            log_path=f'{SKYCONF_DIR}/link_controller.log')

        # Thread safe queue for Informers to append events to.
        self.event_queue: queue.Queue = queue.Queue()
        self.post_init_hook()

    def post_init_hook(self):

        def add_callback_fn(event):
            self.event_queue.put(event)

        def delete_callback_fn(event):
            self.event_queue.put(event)

        self.link_informer = Informer(LinkAPI(), logger=self.logger)
        self.link_informer.add_event_callbacks(
            add_event_callback=add_callback_fn,
            delete_event_callback=delete_callback_fn)
        self.link_informer.start()

        self.cluster_informer = Informer(ClusterAPI(), logger=self.logger)
        self.cluster_informer.start()

    def run(self):
        self.logger.info(
            "Running Link controller - Creates and deletes links across clusters."
        )
        super().run()

    def controller_loop(self):
        # Blocks until there is at least 1 element in the queue or until timeout.
        event = self.event_queue.get()
        event_type = event.event_type
        event_object = event.object
        if isinstance(event_object, Link):
            source = event_object.spec.source_cluster
            target = event_object.spec.target_cluster
            skip_update = False
            try:
                if event_type == WatchEventEnum.ADD:
                    self.logger.info(
                        'Creating link between clusters: [%s, %s]', source,
                        target)
                    self._create_link(source, target)
                    link_status = LinkStatusEnum.ACTIVE.value
                elif event_type == WatchEventEnum.DELETE:
                    self.logger.info(
                        'Deleting link between clusters: [%s, %s]', source,
                        target)
                    self._delete_link(source, target)
                    skip_update = True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                link_status = LinkStatusEnum.FAILED.value

            # Update the link status.
            if not skip_update:
                event_object.status.update_status(link_status)
                LinkAPI().update(event_object.model_dump(mode="json"))

    def _create_link(self, source: str, target: str) -> bool:
        """Creates a link between two clusters. Returns True if successful, False otherwise."""
        clusters_cache = self.cluster_informer.get_cache()
        source_cluster_manager = setup_cluster_manager(clusters_cache[source])
        target_cluster_manager = setup_cluster_manager(clusters_cache[target])
        try:
            return create_link(source_manager=source_cluster_manager,
                               target_manager=target_cluster_manager)
        except (subprocess.CalledProcessError,
                subprocess.TimeoutExpired) as error:
            self.logger.error(traceback.format_exc())
            self.logger.error('Failed to create link between clusters.')
            raise error

    def _delete_link(self, source: str, target: str) -> bool:
        """Deletes a link between two clusters. Returns True if successful, False otherwise."""
        clusters_cache = self.cluster_informer.get_cache()
        source_cluster_manager = setup_cluster_manager(clusters_cache[source])
        target_cluster_manager = setup_cluster_manager(clusters_cache[target])
        try:
            return delete_link(source_manager=source_cluster_manager,
                               target_manager=target_cluster_manager)
        except (subprocess.CalledProcessError,
                subprocess.TimeoutExpired) as error:
            self.logger.error(traceback.format_exc())
            self.logger.error("Failed to delete link between clusters.")
            raise error


if __name__ == "__main__":
    hc = LinkController()
    hc.run()
