#! /bin/bash
SCRIPT_DIR=$(pwd)

function pull_and_install_clusterlink {
    git clone https://github.com/praveingk/clusterlink.git
    cd clusterlink
    mkdir -p deploy/
    make prereqs
    go mod tidy
    make build
    cd -
    export PATH=$PATH:$SCRIPT_DIR/clusterlink/bin
}

pull_and_install_clusterlink