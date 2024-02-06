#! /bin/bash
install_dir="~/.skym/cl"

pull_and_install_clusterlink() {
    local dir=$1
    git clone https://github.com/praveingk/clusterlink.git $dir/clusterlink
    cd $dir/clusterlink
    mkdir -p deploy/
    make prereqs
    go mod tidy
    make build
    cd -
    export PATH=$PATH:$dir/clusterlink/bin
}

mkdir -p $install_dir
pull_and_install_clusterlink $install_dir