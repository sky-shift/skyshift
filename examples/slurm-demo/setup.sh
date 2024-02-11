#!/bin/bash
HOST=$(hostname -i | sed -e 's/^\([^[:space:]]*\).*/\1/')
echo $HOST
echo "HOST=${HOST}" > .env