#! /bin/bash
SCRIPT_DIR=$(pwd)

pull_and_install_clusterlink() {
    local dir=$1
    git clone https://github.com/praveingk/clusterlink.git $dir/clusterlink
    cd $dir/clusterlink
    mkdir -p deploy/
    make prereqs
    go mod tidy
    make build
    cd -
    export PATH=$PATH:$SCRIPT_DIR/clusterlink/bin
}

pull_and_install_clusterlink $1