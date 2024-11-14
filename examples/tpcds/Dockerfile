FROM apache/spark:latest

USER root

RUN apt-get update && \
    apt-get install -y gcc make git bison flex

RUN git clone https://github.com/databricks/tpcds-kit.git && \
    cd tpcds-kit/tools && \
    make OS=LINUX

COPY TpcdsBenchmark-assembly-0.1.jar /opt/spark/jars/

USER 185
