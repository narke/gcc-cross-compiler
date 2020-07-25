#!/usr/bin/env python3
""" Cross-compiler toolchain build script

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

    If '--install no' is present, the toolchain still uses the
    CROSS_PREFIX as the target directory but the installation
    copies the files into PKG/ subdirectory without affecting
    the actual root file system. That is only useful if you do
    not want to run the script under the super user."""

# Copyright (c) 2016-2020 Konstantin Tcholokachvili
# All rights reserved.
#
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Credits:
# This script is inspired by toolchain.sh made by Martin Decky for HelenOS
# project.

import os
import sys
import ftplib
import shutil
import pathlib
import tarfile
import hashlib
import tempfile
import argparse
import subprocess


# Toolchain versions
BINUTILS_VERSION = '2.34'
GCC_VERSION = '10.2.0'
GDB_VERSION = '9.2'

BASEDIR = os.getcwd()
BINUTILS_TARBALL = 'binutils-{}.tar.xz'.format(BINUTILS_VERSION)
GCC_TARBALL = 'gcc-{}.tar.xz'.format(GCC_VERSION)
GDB_TARBALL = 'gdb-{}.tar.xz'.format(GDB_VERSION)

INSTALL_DIR = BASEDIR + '/PKG'

BINUTILS_CHECKSUM = '664ec3a2df7805ed3464639aaae332d6'
GCC_CHECKSUM = 'e9fd9b1789155ad09bcf3ae747596b50'
GDB_CHECKSUM = 'db95524e554870209ab7d9f8fd8dc557'

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

TARGETS = {
    'amd64': 'amd64-linux-gnu',
    'arm32': 'arm-linux-gnueabi',
    'ia32': 'i686-pc-linux-gnu',
    'ia64': 'ia64-pc-linux-gnu',
    'mips32': 'mipsel-linux-gnu',
    'mips32eb': 'mips-linux-gnu',
    'mips64': 'mips64el-linux-gnu',
    'ppc32': 'ppc-linux-gnu',
    'ppc64': 'ppc64-linux-gnu',
    'sparc32': 'sparc-leon3-linux-gnu',
    'sparc64': 'sparc64-linux-gnu'
}


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


def download(toolname, tarball):
    """Downlaod a source archive."""
    if toolname == 'gcc':
        path = '/gnu/gcc/gcc-{}/'.format(GCC_VERSION)
    else:
        path = '/gnu/{}/'.format(toolname)

    try:
        ftp = ftplib.FTP('ftp.gnu.org')
        ftp.login()
        ftp.cwd(path)
        with open('{}'.format(tarball), 'wb') as ftpfile:
            ftp.retrbinary('RETR {}'.format(tarball), ftpfile.write)
        ftp.quit()
    except ftplib.all_errors:
        print('Error: Downoad of {} failed'.format(tarball))
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

    tools = {
        'binutils':
        {
            'tarball': BINUTILS_TARBALL,
            'checksum': BINUTILS_CHECKSUM
        },
        'gcc':
        {
            'tarball': GCC_TARBALL,
            'checksum': GCC_CHECKSUM
        },
        'gdb':
        {
            'tarball': GDB_TARBALL,
            'checksum': GDB_CHECKSUM
        }
    }

    for toolname in tools:
        if not os.path.isfile(tools[toolname]['tarball']):
            download(toolname, tools[toolname]['tarball'])
            check_integrity(tools[toolname]['tarball'],
                            tools[toolname]['checksum'])


def set_target_from_platform(platform):
    """Sets the triplet *-linux-* as target."""
    return TARGETS[platform]


def cleanup_dir(path):
    """Remove a directory ecursively."""
    if os.path.isdir(path):
        shutil.rmtree(path)


def create_dir(path):
    """Create a directory within a given path."""
    if not os.path.isdir(path):
        print('>>> Creating directory: {}'.format(path))
        pathlib.Path(path).mkdir(parents=True, exist_ok=True)


def unpack_tarball(tarball):
    """Extract file from a tarball."""
    with tarfile.open(tarball) as tar:
        tar.extractall('.')


def cleanup_previous_build(install, prefix, work_directory, obj_directory):
    """Remove files from the previous build."""

    print('>>> Removing previous content')
    if install:
        cleanup_dir(prefix)
        create_dir(prefix)

    cleanup_dir(work_directory)
    create_dir(work_directory)
    create_dir(obj_directory)


def unpack_tarballs(work_directory):
    """Unpack tarballs containing source code."""

    print('>>> Unpacking tarballs')
    os.chdir(work_directory)

    unpack_tarball(BASEDIR + '/' + BINUTILS_TARBALL)
    unpack_tarball(BASEDIR + '/' + GCC_TARBALL)
    unpack_tarball(BASEDIR + '/' + GDB_TARBALL)


def build_binutils(install, nb_cores, binutils_directory, target, prefix):
    """Build binutils."""

    os.chdir(binutils_directory)

    try:
        subprocess.check_call(['./configure', '--target={}'.format(target),
                               '--prefix={}'.format(prefix),
                               '--program-prefix={}-'.format(target),
                               '--disable-nls', '--disable-werror'])
    except subprocess.CalledProcessError:
        print('Error: binutils headers checking failed')
        sys.exit()

    os.environ['CFLAGS'] = '-Wno-error'

    try:
        subprocess.check_call(['make', '-j', str(nb_cores), 'all'])
    except subprocess.CalledProcessError:
        print('Error: binutils compilation failed')
        sys.exit()

    if install:
        cmd = ['make', 'install']
    else:
        cmd = ['make', 'install', 'DESTDIR={}'.format(INSTALL_DIR)]

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        print('Error: binutils installation failed ')
        sys.exit()


def build_gcc(*args):
    """Build GCC."""

    install, nb_cores, obj_directory, prefix, gcc_directory, target = args

    os.chdir(obj_directory)

    try:
        subprocess.check_call(['{}/configure'.format(gcc_directory),
                               '--target={}'.format(target),
                               '--prefix={}'.format(prefix),
                               '--program-prefix={}-'.format(target),
                               '--with-gnu-as', '--with-gnu-ld', '--disable-nls',
                               '--disable-threads', '--enable-languages=c',
                               '--disable-multilib', '--disable-libgcj',
                               '--without-headers', '--disable-shared', '--enable-lto',
                               '--disable-werror'])
    except subprocess.CalledProcessError:
        print('Error: gcc headers checking failed')
        sys.exit()

    try:
        subprocess.check_call(['make', '-j', str(nb_cores), 'all-gcc'])
    except subprocess.CalledProcessError:
        print('Error: gcc compilation failed')
        sys.exit()

    if install:
        cmd = ['make', 'install-gcc']
    else:
        cmd = ['make', 'install-gcc', 'DESTDIR={}'.format(INSTALL_DIR)]

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        print('Error: gcc installation failed')
        sys.exit()


def build_gdb(install, nb_cores, gdb_directory, target, prefix):
    """Build GDB."""

    os.chdir(gdb_directory)

    try:
        subprocess.check_call(['./configure', '--target={}'.format(target),
                               '--prefix={}'.format(prefix),
                               '--program-prefix={}-'.format(target),
                               '--enable-werror=no'])
    except subprocess.CalledProcessError:
        print('Error: gdb headers checking failed')
        sys.exit()

    try:
        subprocess.check_call(['make', '-j', str(nb_cores), 'all'])
    except subprocess.CalledProcessError:
        print('Error: gdb compilation failed')
        sys.exit()

    if install:
        cmd = ['make', 'install']
    else:
        cmd = ['make', 'install', 'DESTDIR={}'.format(INSTALL_DIR)]

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        print('Error: gdb installatior failed')
        sys.exit()


def build_target(platform, install, nb_cores):
    """Cross-compile gcc toolchain for a given architecture."""

    work_directory = BASEDIR + '/' + platform
    binutils_directory = work_directory + '/binutils-' + BINUTILS_VERSION
    gcc_directory = work_directory + '/gcc-' + GCC_VERSION
    obj_directory = work_directory + '/gcc-obj'
    gdb_directory = work_directory + '/gdb-' + GDB_VERSION

    target = set_target_from_platform(platform)

    if os.environ.get('CROSS_PREFIX'):
        cross_prefix = os.environ['CROSS_PREFIX']
    else:
        cross_prefix = '/usr/local/cross/'

    prefix = cross_prefix + platform

    os.environ['PATH'] += ':{0}{1}/bin'.format(INSTALL_DIR, prefix)
    os.environ['PATH'] += ':{0}/bin'.format(prefix)

    cleanup_previous_build(install, prefix, work_directory, obj_directory)
    unpack_tarballs(work_directory)

    build_binutils(install, nb_cores, binutils_directory, target, prefix)
    build_gcc(install, nb_cores, obj_directory, prefix, gcc_directory, target)
    build_gdb(install, nb_cores, gdb_directory, target, prefix)

    os.chdir(BASEDIR)
    print('>>> Cleaning up')
    cleanup_dir(work_directory)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--arch',
                        help='Target architecture',
                        type=str,
                        choices=['amd64', 'arm32', 'ia32', 'ia64', 'mips32',
                                 'mips32eb', 'mips64', 'ppc32', 'ppc64',
                                 'sparc32', 'sparc64'],
                        required=True)
    parser.add_argument('-i', '--install',
                        help='Install in /usr/local/cross or just '
                        'keep cross-compiled binaries into the build directory',
                        type=str,
                        choices=['yes', 'no'],
                        required=True)
    parser.add_argument('-c', '--cores',
                        help='Number of CPU cores',
                        type=int, required=False, default=1)

    arguments = parser.parse_args()

    target_platform = arguments.arch
    INSTALL = arguments.install == 'yes'
    nb_cpu_cores = arguments.cores - 1

    check_headers()
    prepare()
    build_target(target_platform, INSTALL, nb_cpu_cores)

    MSG = 'installed' if arguments.install == 'yes' else 'built'
    print('>>> Cross-compiler for {} is now {}.'.format(target_platform, MSG))
