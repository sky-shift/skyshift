"""
#Utility that will always be running act as a heartbeat for slurm
"""
import os
import sys
import requests_unixsocket
import socket
import requests
import json
import socket
import logging
import threading
API_SERVER_HOST = 'localhost'
API_SERVER_PORT = 50052
class SlurmMonitor ( object ):
    def __init__ (self, slurm_port=os.environ["SLURMRESTD"], openAPI_ver=os.environ["SLURMOPENAPI"], isUnixSocket=False):
        if slurm_port == None:
            raise Exception("Please provide the unix port listening on, or set it in environment variable $SLURMRESTD")
            return
        if openAPI_ver == None:
            raise Exception("Please provide the openapi version slurmrestd is configured with, or set it in environment variable $SLURMOPENAPI")
            return    
        self.slurm_port = slurm_port
        self.openAPI_ver = openAPI_ver
        self.session= requests_unixsocket.Session()
        if isUnixSocket:
            self.port = "http+unix://" + self.slurm_port.replace("/", "%2F")
        else:
            self.port=slurm_port
        self.port = self.port + "/slurm/" + self.openAPI_ver
        #print(self.port)

        self.retry_limit = 3
        self.query_time = 3

    def slurmHeartBeat(self):
        print("hi")

    def run(self):
        try:
if __name__ == "main":
    server = SlurmMonitor(isUnixSocket=True)
        

