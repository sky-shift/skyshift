import json

import pytest
import yaml


class TestManagerTemplate(object):

    def test_cluster_resources(self):
        raise NotImplementedError

    def test_allocatable_resources(self):
        raise NotImplementedError

    def test_get_cluster_status(self):
        raise NotImplementedError

    def test_get_jobs_status(self):
        raise NotImplementedError

    def test_submit_job(self):
        raise NotImplementedError

    def test_delete_job(self):
        raise NotImplementedError

    def test_get_accelerator_types(self):
        raise NotImplementedError

    def test_convert_yaml(self):
        raise NotImplementedError
