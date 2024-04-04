# Use an official Python runtime as a parent image
FROM python:3.10

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY . /usr/src/app


RUN pip install --upgrade pip && pip install --no-cache-dir -e .[server,dev]

RUN curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh

RUN [ $(uname -m) = x86_64 ] && curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.22.0/kind-linux-amd64 && \
    chmod +x ./kind && \
    mv ./kind /usr/local/bin/kind

RUN kind --version

RUN kind create cluster --name dummy
    