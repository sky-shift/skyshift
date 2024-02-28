from setuptools import setup

setup(
    name="skyflow",
    version="0.0",
    description="Sky Manager",
    packages=["skyflow"],
    install_requires=[
        "Click",
        "click_aliases",
        "etcd3",
        "kubernetes",
        "passlib",
        "protobuf==3.20.0",
        "python-jose",
        "pydantic>=2.5.0",
        "pytest",
        "pyyaml",
        "requests>=2.31.0",
        "rich",
        "tabulate",
        "types-passlib",
        "types-psutil",
        "types-tabulate",
        "types-PyYAML",
        "types-requests",
        "skypilot[aws,gcp,azure,kubernetes]",
    ],
    extras_require={
        "server": [
            "etcd3", "fastapi", "uvicorn[standard]", "pydantic>=2.5.0",
            'jsonpatch'
        ],
        "dev": [
            "yapf==0.32.0", "pylint==2.8.2", "pylint-quotes==0.2.3",
            "mypy==1.8.0"
        ],
    },
    entry_points={
        "console_scripts": [
            "skyctl = skyflow.cli.cli:cli",
        ],
    },
    zip_safe=False,
)
