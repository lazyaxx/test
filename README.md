mkdir -p ~/Saketh/Python312
cd ~
wget https://www.python.org/ftp/python/3.12.10/Python-3.12.10.tgz
tar -xzf Python-3.12.10.tgz
cd Python-3.12.10
./configure --prefix=$HOME/Saketh/Python312 --enable-optimizations
make -j$(nproc)
make altinstall
mkdir -p ~/bin
ln -s ~/Saketh/Python312/bin/python3.12 ~/bin/python3.12
echo 'export PATH=$HOME/Saketh/Python312/bin:$HOME/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
python3.12 --version
