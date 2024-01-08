from setuptools import setup

setup(name='skyflow',
      version='0.0',
      description='Sky Manager',
      packages=['skyflow'],
      install_requires=[
          'Click',
          'click_aliases',
          'etcd3',
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
              'skyctl = skyflow.cli.cli:cli',
          ],
      },
      zip_safe=False)
