#!/bin/bash
# setup_and_run_spark.sh

echo "Starting environment setup..."

# UID/GID Setup
myuid=$(id -u)
mygid=$(id -g)
uidentry=$(getent passwd $myuid)

if [ -z "$uidentry" ] ; then
    if [ -w /etc/passwd ] ; then
        echo "$myuid:x:$myuid:$mygid:anonymous uid:$SPARK_HOME:/bin/false" >> /etc/passwd
    else
        echo "Container ENTRYPOINT failed to add passwd entry for anonymous UID"
    fi
fi

# JAVA_HOME Setup
if [ -z "$JAVA_HOME" ]; then
  JAVA_HOME=$(java -XshowSettings:properties -version 2>&1 > /dev/null | grep 'java.home' | awk '{print $3}')
fi

# SPARK_CLASSPATH Setup
SPARK_CLASSPATH="${SPARK_HOME}/jars/*"

if [ -n "$SPARK_EXTRA_CLASSPATH" ]; then
  SPARK_CLASSPATH="$SPARK_CLASSPATH:$SPARK_EXTRA_CLASSPATH"
fi

# HADOOP_HOME and SPARK_DIST_CLASSPATH Setup
if [ -n "${HADOOP_HOME}"  ] && [ -z "${SPARK_DIST_CLASSPATH}"  ]; then
  export SPARK_DIST_CLASSPATH="$($HADOOP_HOME/bin/hadoop classpath)"
fi

# Classpath Additions
if [ -n "$HADOOP_CONF_DIR" ]; then
  SPARK_CLASSPATH="$HADOOP_CONF_DIR:$SPARK_CLASSPATH";
fi

if [ -n "$SPARK_CONF_DIR" ]; then
  SPARK_CLASSPATH="$SPARK_CONF_DIR:$SPARK_CLASSPATH";
elif [ -n "$SPARK_HOME" ]; then
  SPARK_CLASSPATH="$SPARK_HOME/conf:$SPARK_CLASSPATH";
fi

SPARK_CLASSPATH="$SPARK_CLASSPATH:$PWD"

# Now run spark-submit
/opt/spark/bin/spark-submit --class org.apache.spark.examples.SparkPi /opt/spark/examples/src/main/python/pi.py
