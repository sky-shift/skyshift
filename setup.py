import requests
from setuptools import setup, Command
from setuptools.command.install import install
from setuptools.command.develop import develop
import subprocess


def check_and_install_etcd():
    result = subprocess.run('ps aux | grep "[e]tcd"', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return_code = result.returncode
    if return_code == 0:
        print('[Installer] ETCD is running.')
    else:
        print("[Installer] ETCD is not running, automatically installing ETCD.")
        # Install ETCD (platform-specific code goes here)
        # Start ETCD in background (platform-specific code goes here)
        subprocess.run('./setup/etcd_installation.sh', shell=True)


class CustomDevelopCommand(develop):
    def run(self):
        check_and_install_etcd()
        develop.run(self)


class CustomInstallCommand(install):
    def run(self):
        check_and_install_etcd()
        install.run(self)


setup(name='sky_manager',
      version='0.0',
      description='Sky Manager',
      packages=['sky_manager'],
      cmdclass={
        'install': CustomInstallCommand,
        'develop': CustomDevelopCommand,
      },
      install_requires=[
          'Click',
      ],
      entry_points={
          'console_scripts': [
              'skyctl = sky_manager.cli:cli',
          ],
      },
      zip_safe=False)
