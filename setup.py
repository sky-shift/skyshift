"""Skyshift package setup script."""
from setuptools import setup

setup(
    name="skyshift",
    version="0.0",
    description="Sky Manager",
    packages=["skyshift"],
    install_requires=[
        "bcrypt==4.0.1",
        "Click",
        "click_aliases",
        "etcd3@ git+https://github.com/sky-shift/python-etcd3.git@master#egg=etcd3",
        "fastapi",
        "kubernetes",
        "passlib",
        "protobuf==3.20.2",
        "python-jose",
        "pydantic>=2.5.0",
        "pydantic[email]>=2.5.0",
        'python-multipart',
        "pytest",
        "pyyaml",
        "requests>=2.31.0",
        "rich",
        "skypilot==0.5.0",
        "paramiko",
        "tabulate",
        "types-passlib",
        "types-paramiko",
        "types-psutil",
        "types-tabulate",
        "types-PyYAML",
        "types-requests",
        "websockets",
        "halo",
        "tqdm",
        "rapidfuzz",
        "regex",
        "paramiko",
        "ray",
    ],
    extras_require={
        "server": [
            "etcd3",
            "uvicorn[standard]",
            'jsonpatch',
            "pyjwt",
        ],
        "dev": [
            "yapf==0.32.0", "pylint==2.8.2", "pylint-quotes==0.2.3",
            "mypy==1.8.0"
        ],
    },
    entry_points={
        "console_scripts": [
            "skyctl = skyshift.cli.cli:cli",
        ],
    },
    zip_safe=False,
)
