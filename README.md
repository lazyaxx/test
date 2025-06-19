# Install libffi locally
cd ~
wget ftp://sourceware.org/pub/libffi/libffi-3.2.1.tar.gz
tar -xzf libffi-3.2.1.tar.gz
cd libffi-3.2.1
./configure --prefix=$HOME/Saketh/libffi
make && make install

# Set environment variables
export LD_LIBRARY_PATH=$HOME/Saketh/libffi/lib64:$HOME/Saketh/libffi/lib:$LD_LIBRARY_PATH
export PKG_CONFIG_PATH=$HOME/Saketh/libffi/lib/pkgconfig:$PKG_CONFIG_PATH

# Rebuild Python with libffi support
cd ~/Python-3.12.10
make clean
./configure --prefix=$HOME/Saketh/Python312 \
    --enable-optimizations \
    --with-system-ffi \
    CPPFLAGS="-I$HOME/Saketh/libffi/include" \
    LDFLAGS="-L$HOME/Saketh/libffi/lib64 -L$HOME/Saketh/libffi/lib" \
    PKG_CONFIG_PATH="$HOME/Saketh/libffi/lib/pkgconfig"
make -j$(nproc)
make altinstall

# Test the installation
python3.12 -c "import ctypes; print('ctypes works!')"

