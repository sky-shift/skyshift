from setuptools import setup

setup(name='sky_manager',
      version='0.0',
      description='Sky Manager',
      packages=['sky_manager'],
      install_requires=[
          'Click',
      ],
      entry_points={
          'console_scripts': [
              'skym = sky_manager.cli:cli',
          ],
      },
      zip_safe=False)
