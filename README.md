# GCC cross-compiler building script

Supported architectures:

        Cross-compiler toolchain build script
        Possible target platforms are:
         aarch64    ARM64
         amd64      AMD64 (x86-64, x64)
         arm32      ARM
         armhf      ARM hard float
         ia32       IA-32 (x86, i386)
         ia64       IA-64 (Itanium)
         mips32     MIPS little-endian 32b
         mips32eb   MIPS big-endian 32b
         mips64     MIPS little-endian 64b
         ppc32      32-bit PowerPC
         ppc64      64-bit PowerPC
         sparc32    SPARC V8
         sparc64    SPARC V9
         lm32       LatticeMico32

        The toolchain is installed into directory specified by the
        CROSS_PREFIX environment variable. If the variable is not
        defined, /usr/local/cross/ is used as default.
        
        If '--install no' is present, the toolchain still uses the
        CROSS_PREFIX as the target directory but the installation
        copies the files into PKG/ subdirectory without affecting
        the actual root file system. That is only useful if you do
        not want to run the script under the super user.
        
        If '--enable-cxx' is present, C++ tools (e. g. g++) are built.
    

# Dependencies to install on Debian-based distros

    sudo apt install sed flex bison gzip gettext zlib1g texinfo libelf-dev libgomp1 make tar libgmp-dev libmpfr-dev libmpc-dev libisl-dev build-essential


# Building

All currently available cpu cores are detected and used to build as faster as possible.

**Example 1:** Build a cross-compiler for 32-bit PowerPC without installing:

     ./toolchain.py --arch ppc32 --install no

**Example 2:** Build a cross-compiler for 64-bit ARM with C++ support without installing:

     ./toolchain.py --arch aarch64 --install no --enable-cxx

**Example 3:**  Build and install a cross-compiler for 32-bit ARM (default install directory is
/usr/local/cross, specify another one by exporting CROSS_PREFIX environment
variable), note that you need 'sudo' to install:

     sudo ./toolchain.py --arch arm32 --install yes

