#! /bin/bash
install_dir=~/.skyconf/cl

pull_and_install_clusterlink() {
    local dir=$1
    if [ ! -d $dir/clusterlink ]; then
        git clone https://github.com/praveingk/clusterlink.git $dir/clusterlink
    fi

    if [ ! -f $dir/clusterlink/bin/cl-adm ]; then
        cd $dir/clusterlink
        make prereqs
        go mod tidy
        make build
        cd -
    fi
    export PATH=$PATH:$dir/clusterlink/bin
}

mkdir -p $install_dir
pull_and_install_clusterlink $install_dir