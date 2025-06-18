python_config() {
    export PYTHON_VER="3.12.10"
    export PYTHON_VER_SHORT="3.12"
    cd ~
    rm -rf ~/python && mkdir -p ~/python
    echo 'export PATH=~/python/bin:$PATH' >> ~/.bashrc
    source ~/.bashrc
    wget "https://www.python.org/ftp/python/${PYTHON_VER}/Python-${PYTHON_VER}.tgz"
    tar -zxf ~/Python-${PYTHON_VER}.tgz
    cd ~/Python-${PYTHON_VER}/
    ./configure --enable-optimizations --prefix=$HOME/python
    make -j 4
    make altinstall
    ln -s ~/python/bin/python${PYTHON_VER_SHORT} ~/python/bin/python3
    ln -s ~/python/bin/pip${PYTHON_VER_SHORT} ~/python/bin/pip3
    cd ~ && rm -rf ~/Python-${PYTHON_VER}*
    ~/python/bin/python3 --version
}

python_config
