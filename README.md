# GCC cross-compiler building script

Supported architectures:

    narke@vemst ~/P/gcc-cross-compiler> ./toolchain.py 
        Cross-compiler toolchain build script
        Syntax:
         ./toolchain.py [--no-install] <platform>
        Possible target platforms are:
         amd64      AMD64 (x86-64, x64)
         arm32      ARM
         ia32       IA-32 (x86, i386)
         ia64       IA-64 (Itanium)
         mips32     MIPS little-endian 32b
         mips32eb   MIPS big-endian 32b
         mips64     MIPS little-endian 64b
         ppc32      32-bit PowerPC
         ppc64      64-bit PowerPC
         sparc32    SPARC V8
         sparc64    SPARC V9

        The toolchain is installed into directory specified by the
        CROSS_PREFIX environment variable. If the variable is not
        defined, /usr/local/cross/ is used as default.
        
        If --no-install is present, the toolchain still uses the
        CROSS_PREFIX as the target directory but the installation
        copies the files into PKG/ subdirectory without affecting
        the actual root file system. That is only useful if you do
        not want to run the script under the super user.

Build a cross-compiler for 32-bit PowerPC without installing:

     ./toolchain.py --no-install ppc32

Build and install a cross-compiler for 32-bit ARM (default install directory is
/usr/local/cross, specify another one by exporting CROSS_PREFIX environment
variable):

     ./toolchain.py arm32
    
