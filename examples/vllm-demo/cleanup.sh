#!/bin/bash
skyctl delete endpoints vllm-service
skyctl delete service vllm-service

skyctl delete link clink
skyctl delete job vllm