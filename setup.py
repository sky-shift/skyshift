import requests
from setuptools import setup, Command
from setuptools.command.install import install
from setuptools.command.develop import develop
import subprocess


def check_and_install_etcd():
    try:
        subprocess.run(["etcd", "--version"], check=True)
        print("[Preinstaller] ETCD is running.")
    except requests.ConnectionError:
        print("[Preinstaller] ETCD is not running, automatically installing ETCD.")
        # Install ETCD (platform-specific code goes here)
        # Start ETCD in background (platform-specific code goes here)
        subprocess.call(['./etcd_installation.sh'])


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
