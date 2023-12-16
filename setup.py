from setuptools import setup

setup(name='sky_manager',
      version='0.0',
      description='Sky Manager',
      packages=['sky_manager'],
      install_requires=[
          'Click',
          'kubernetes', 
          'protobuf==3.20.0',
          'pydantic>=2.5.0',
          'pytest',
          'pyyaml',
          'requests',
          'rich',
          'tabulate',
          'skypilot[aws,gcp,azure,kubernetes]',
      ],
      extras_require={
          'server': ['etcd3','fastapi', 'uvicorn[standard]', 'pydantic>=2.5.0'],
      },
      entry_points={
          'console_scripts': [
              'skyctl = sky_manager.cli:cli',
          ],
      },
      zip_safe=False)
