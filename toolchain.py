#!/usr/bin/env python3
""" Make a cross-compiler."""

#
# Copyright (c) 2016 Konstantin Tcholokachvili
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# - Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
# - Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
# - The name of the author may not be used to endorse or promote products
#   derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

#
# Credits:
# This script is inspired by toolchain.sh made by Martin Decky for HelenOS
# project.
#

import os
import sys
import hashlib
import tempfile
import subprocess


# Toolchain versions
BINUTILS_VERSION = '2.29'
BINUTILS_RELEASE = ''
GCC_VERSION = '7.2.0'
GDB_VERSION = '8.0.1'

BASEDIR = os.getcwd()
BINUTILS = 'binutils-{0}{1}.tar.bz2'.format(BINUTILS_VERSION, BINUTILS_RELEASE)
GCC = 'gcc-{}.tar.gz'.format(GCC_VERSION)
GDB = 'gdb-{}.tar.gz'.format(GDB_VERSION)

REAL_INSTALL = True
INSTALL_DIR = BASEDIR + '/PKG'
TARGET_PLATFORM = ''

BINUTILS_SOURCE = 'ftp://ftp.gnu.org/gnu/binutils/'
GCC_SOURCE = 'ftp://ftp.gnu.org/gnu/gcc/gcc-{}/'.format(GCC_VERSION)
GDB_SOURCE = 'ftp://ftp.gnu.org/gnu/gdb/'

BINUTILS_CHECKSUM = '23733a26c8276edbb1168c9bee60e40e'
GCC_CHECKSUM = '2e4be17c604ea555e0dff4a8f81ffe44'
GDB_CHECKSUM = 'bb45869f8126a84ea2ba13a8c0e7c90e'

GMP_MAIN = """
#define GCC_GMP_VERSION_NUM(a, b, c) \
        (((a) << 16L) | ((b) << 8) | (c))

#define GCC_GMP_VERSION \
        GCC_GMP_VERSION_NUM(__GNU_MP_VERSION, __GNU_MP_VERSION_MINOR, __GNU_MP_VERSION_PATCHLEVEL)

#if GCC_GMP_VERSION < GCC_GMP_VERSION_NUM(4, 3, 2)
        choke me
#endif
"""

MPFR_MAIN = """
#if MPFR_VERSION < MPFR_VERSION_NUM(2, 4, 2)
        choke me
#endif
"""

MPC_MAIN = """
#if MPC_VERSION < MPC_VERSION_NUM(0, 8, 1)
        choke me
#endif
"""

ISL_MAIN = """
isl_ctx_get_max_operations (isl_ctx_alloc ());
"""

TARGETS = {'amd64': 'amd64-linux-gnu',
           'arm32': 'arm-linux-gnueabi',
           'ia32': 'i686-pc-linux-gnu',
           'ia64': 'ia64-pc-linux-gnu',
           'mips32': 'mipsel-linux-gnu',
           'mips32eb': 'mips-linux-gnu',
           'mips64': 'mips64el-linux-gnu',
           'ppc32': 'ppc-linux-gnu',
           'ppc64': 'ppc64-linux-gnu',
           'sparc32': 'sparc-leon3-linux-gnu',
           'sparc64': 'sparc64-linux-gnu'}


def check_header(dependency, header, body):
    """Check the presence of a header file needed to compile sources."""
    code = """
    #include %s

    int main()
    {
        %s
        return 0;
    }
    """ % (header, body)

    filename = tempfile.NamedTemporaryFile(suffix='.c')
    filename.write(code.encode())

    try:
        subprocess.check_call(['cc', '-c', '-o', '{}.o'.format(filename.name[:-2]),
                               '{}'.format(filename.name)])
        os.unlink('{}.o'.format(filename.name[:-2]))
    except subprocess.CalledProcessError:
        print('{0} of {1} not found'.format(header, dependency))
        sys.exit()


def check_headers():
    """Check that all required headers are present."""
    check_header('GMP', '<gmp.h>', GMP_MAIN)
    check_header('MPFR', '<mpfr.h>', MPFR_MAIN)
    check_header('MPC', '<mpc.h>', MPC_MAIN)
    check_header('isl', '<isl/ctx.h>', ISL_MAIN)


def show_dependencies():
    """Notice informing about dependencies for a successful compilation."""

    message = """IMPORTANT NOTICE:

    For a successful compilation and use of the cross-compiler
    toolchain you need at least the following dependencies.

    Please make sure that the dependencies are present in your
    system. Otherwise the compilation process might fail after
    a few seconds or minutes."

    - SED, AWK, Flex, Bison, gzip, bzip2, Bourne Shell
    - gettext, zlib, Texinfo, libelf, libgomp
    - GNU Make, Coreutils, Sharutils, tar
    - GNU Multiple Precision Library (GMP)
    - MPFR
    - MPC
    - integer point manipulation library (isl)
    - native C and C++ compiler, assembler and linker
    - native C and C++ standard library with headers"""

    print(message)


def download(url, archive):
    """Downlaod a source archive with wget."""
    if not os.path.isfile(archive):
        try:
            subprocess.call(['wget', '-c', url+archive])
        except subprocess.CalledProcessError:
            print('Error: Download of {} failed'.format(archive))
            sys.exit()


def check_integrity(archive, checksum):
    """Check the md5 checksum of a tarball."""
    with open(archive, 'rb') as tarball:
        if hashlib.md5(tarball.read()).hexdigest() != checksum:
            print('Error: Wrong checksum for {}'.format(archive))
            sys.exit()


def prepare():
    """Prepare the compilation: get the sources and check their integrity."""
    show_dependencies()

    download(BINUTILS_SOURCE, BINUTILS)
    check_integrity(BINUTILS, BINUTILS_CHECKSUM)

    download(GCC_SOURCE, GCC)
    check_integrity(GCC, GCC_CHECKSUM)

    download(GDB_SOURCE, GDB)
    check_integrity(GDB, GDB_CHECKSUM)


def set_target_from_platform():
    """Sets the triplet *-linux-* as target."""
    return TARGETS[TARGET_PLATFORM]


def cleanup_dir(path):
    """Remove a directory ecursively."""
    if os.path.isdir(path):
        try:
            subprocess.call(['rm', '-rf', path])
        except subprocess.CalledProcessError:
            print('Error: Problem while removing {}'.format(path))
            sys.exit()


def create_dir(path):
    """Create a directory within a given path."""
    if not os.path.isdir(path):
        try:
            subprocess.call(['mkdir', '-p', path])
        except subprocess.CalledProcessError:
            print('Error: Problem while creating {}'.format(path))
            sys.exit()


def unpack_tarball(tarball):
    """Extract file from a tarball."""

    flags = {'.gz': 'xzf', '.xz': 'xJf', '.bz2': 'xjf'}

    _, extension = os.path.splitext(tarball)

    if extension not in flags.keys():
        print('Error: Unsupported extension')
        sys.exit()

    subprocess.call(['tar', flags[extension], tarball])


def cleanup_previous_build(prefix, work_directory, obj_directory):
    """Remove files from the previous build."""

    print('>>> Removing previous content')
    if REAL_INSTALL:
        cleanup_dir(prefix)
    cleanup_dir(work_directory)
    create_dir(work_directory)

    if REAL_INSTALL:
        create_dir(prefix)
    create_dir(obj_directory)


def unpack_tarballs(work_directory):
    """Unpack tarballs containing source code."""

    print('>>> Unpacking tarballs')
    os.chdir(work_directory)

    unpack_tarball(BASEDIR + '/' + BINUTILS)
    unpack_tarball(BASEDIR + '/' + GCC)
    unpack_tarball(BASEDIR + '/' + GDB)


def build_binutils(binutils_directory, target, prefix):
    """Build binutils."""

    os.chdir(binutils_directory)

    subprocess.call(['./configure', '--target={}'.format(target),
                     '--prefix={}'.format(prefix),
                     '--program-prefix={}-'.format(target),
                     '--disable-nls', '--disable-werror'])
    os.environ['CFLAGS'] = '-Wno-error'
    subprocess.call(['make', 'all'])

    if REAL_INSTALL:
        subprocess.call(['make', 'install'])
    else:
        subprocess.call(['make', 'install', 'DESTDIR={}'.format(INSTALL_DIR)])


def build_gcc(obj_directory, prefix, gcc_directory, target):
    """Build GCC."""

    os.chdir(obj_directory)

    subprocess.call(['{}/configure'.format(gcc_directory),
                     '--target={}'.format(target),
                     '--prefix={}'.format(prefix),
                     '--program-prefix={}-'.format(target),
                     '--with-gnu-as', '--with-gnu-ld', '--disable-nls',
                     '--disable-threads', '--enable-languages=c',
                     '--disable-multilib', '--disable-libgcj',
                     '--without-headers', '--disable-shared', '--enable-lto',
                     '--disable-werror'])

    subprocess.call(['make', 'all-gcc'])

    if REAL_INSTALL:
        subprocess.call(['make', 'install-gcc'])
    else:
        subprocess.call(['make', 'install-gcc', 'DESTDIR={}'.format(INSTALL_DIR)])


def build_gdb(gdb_directory, target, prefix):
    """Build GDB."""

    os.chdir(gdb_directory)

    subprocess.call(['./configure', '--target={}'.format(target),
                     '--prefix={}'.format(prefix),
                     '--program-prefix={}-'.format(target),
                     '--enable-werror=no'])

    subprocess.call(['make', 'all'])

    if REAL_INSTALL:
        subprocess.call(['make', 'install'])
    else:
        subprocess.call(['make', 'install', 'DESTDIR={}'.format(INSTALL_DIR)])


def build_target():
    """Cross-compile gcc toolchain for a given architecture."""

    work_directory = BASEDIR + '/' + TARGET_PLATFORM
    binutils_directory = work_directory + '/binutils-' + BINUTILS_VERSION
    gcc_directory = work_directory + '/gcc-' + GCC_VERSION
    obj_directory = work_directory + '/gcc-obj'
    gdb_directory = work_directory + '/gdb-' + GDB_VERSION

    target = set_target_from_platform()

    if os.environ.get('CROSS_PREFIX'):
        cross_prefix = os.environ['CROSS_PREFIX']
    else:
        cross_prefix = '/usr/local/cross/'

    prefix = cross_prefix + TARGET_PLATFORM

    os.environ['PATH'] += ':{0}{1}/bin'.format(INSTALL_DIR, prefix)
    os.environ['PATH'] += ':{0}/bin'.format(prefix)

    cleanup_previous_build(prefix, work_directory, obj_directory)
    unpack_tarballs(work_directory)

    build_binutils(binutils_directory, target, prefix)
    build_gcc(obj_directory, prefix, gcc_directory, target)
    build_gdb(gdb_directory, target, prefix)

    os.chdir(BASEDIR)
    print('>>> Cleaning up')
    cleanup_dir(work_directory)

    print('>>> Cross-compiler for {} installed.'.format(TARGET_PLATFORM))


def show_usage(program_name):
    """Show usage."""

    usage = """
    Cross-compiler toolchain build script

    Syntax:
     {0} [--no-install] <platform>

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
    not want to run the script under the super user.""".format(program_name)

    print(usage)


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        show_usage(sys.argv[0])
        sys.exit()
    elif len(sys.argv) == 2:
        TARGET_PLATFORM = sys.argv[1]
    elif len(sys.argv) == 3:
        if sys.argv[1] == '--no-install':
            REAL_INSTALL = False
        else:
            show_usage(sys.argv[0])
            sys.exit()
        TARGET_PLATFORM = sys.argv[2]

    if TARGET_PLATFORM not in TARGETS.keys():
        print('Unsupported architecure: {}'.format(TARGET_PLATFORM))
        print('Choose one of: {}'.format([arch for arch in TARGETS.keys()]))
        sys.exit()

    check_headers()
    prepare()
    build_target()
