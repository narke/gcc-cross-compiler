#!/usr/bin/env python3
""" Cross-compiler toolchain build script

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
"""

# Copyright (c) 2016-2024 Konstantin Tcholokachvili
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
import logging
import tempfile
import argparse
import subprocess


# Toolchain versions
BINUTILS_VERSION = '2.42'
GCC_VERSION = '14.1.0'
GDB_VERSION = '14.2'

BASEDIR = os.getcwd()
BINUTILS_TARBALL = f'binutils-{BINUTILS_VERSION}.tar.xz'
GCC_TARBALL = f'gcc-{GCC_VERSION}.tar.xz'
GDB_TARBALL = f'gdb-{GDB_VERSION}.tar.xz'

INSTALL_DIR = f'{BASEDIR}/PKG'

BINUTILS_CHECKSUM = 'a075178a9646551379bfb64040487715'
GCC_CHECKSUM = '24195dca80ded5e0551b533f46a4481d'
GDB_CHECKSUM = '4452f575d09f94276cb0a1e95ecff856'

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
    'aarch64': 'aarch64-linux-gnu',
    'amd64': 'amd64-linux-gnu',
    'arm32': 'arm-linux-gnueabi',
    'armhf': 'arm-linux-gnueabihf',
    'ia32': 'i686-pc-linux-gnu',
    'ia64': 'ia64-pc-linux-gnu',
    'mips32': 'mipsel-linux-gnu',
    'mips32eb': 'mips-linux-gnu',
    'mips64': 'mips64el-linux-gnu',
    'ppc32': 'ppc-linux-gnu',
    'ppc64': 'ppc64-linux-gnu',
    'sparc32': 'sparc-leon3-linux-gnu',
    'sparc64': 'sparc64-linux-gnu',
    'lm32': 'lm32-elf'
}

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


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
        subprocess.check_call(['cc', '-c', '-o', f'{filename.name[:-2]}.o',
                               f'{filename.name}'])
        os.unlink(f'{filename.name[:-2]}.o')
    except subprocess.CalledProcessError:
        logger.error(f'{header} of {dependency} not found')
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

    logger.info(message)


def download(toolname, tarball):
    """Downlaod a source archive."""
    if toolname == 'gcc':
        path = f'/gnu/gcc/gcc-{GCC_VERSION}/'
    else:
        path = f'/gnu/{toolname}/'

    try:
        ftp = ftplib.FTP('ftp.gnu.org')
        ftp.login()
        ftp.cwd(path)
        with open(f'{tarball}', 'wb') as ftpfile:
            ftp.retrbinary(f'RETR {tarball}', ftpfile.write)
        ftp.quit()
    except ftplib.all_errors:
        logger.error(f'Error: Downoad of {tarball} failed')
        sys.exit()


def check_integrity(archive, checksum):
    """Check the md5 checksum of a tarball."""
    with open(archive, 'rb') as tarball:
        if hashlib.md5(tarball.read()).hexdigest() != checksum:
            logger.error(f'Error: Wrong checksum for {tarball}')
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
        logger.info(f'>>> Creating directory: {path}')
        pathlib.Path(path).mkdir(parents=True, exist_ok=True)


def unpack_tarball(tarball):
    """Extract file from a tarball."""
    with tarfile.open(tarball) as tar:
        def is_within_directory(directory, target):

            abs_directory = os.path.abspath(directory)
            abs_target = os.path.abspath(target)

            prefix = os.path.commonprefix([abs_directory, abs_target])

            return prefix == abs_directory

        def safe_extract(tar, path=".", members=None, *, numeric_owner=False):

            for member in tar.getmembers():
                member_path = os.path.join(path, member.name)
                if not is_within_directory(path, member_path):
                    raise Exception("Attempted Path Traversal in Tar File")

            tar.extractall(path, members, numeric_owner=numeric_owner)


        safe_extract(tar, ".")


def cleanup_previous_build(install, prefix, work_directory, obj_directory):
    """Remove files from the previous build."""

    logger.info('>>> Removing previous content')
    if install:
        cleanup_dir(prefix)
        create_dir(prefix)

    cleanup_dir(work_directory)
    create_dir(work_directory)
    create_dir(obj_directory)


def unpack_tarballs(work_directory):
    """Unpack tarballs containing source code."""

    logger.info('>>> Unpacking tarballs')
    os.chdir(work_directory)

    unpack_tarball(f'{BASEDIR}/{BINUTILS_TARBALL}')
    unpack_tarball(f'{BASEDIR}/{GCC_TARBALL}')
    unpack_tarball(f'{BASEDIR}/{GDB_TARBALL}')


def build_binutils(install, nb_cores, binutils_directory, target, prefix):
    """Build binutils."""

    os.chdir(binutils_directory)

    try:
        subprocess.check_call(['./configure', f'--target={target}',
                               f'--prefix={prefix}',
                               f'--program-prefix={target}-',
                               '--disable-nls', '--disable-werror'])
    except subprocess.CalledProcessError:
        logger.error('Error: binutils headers checking failed')
        sys.exit()

    os.environ['CFLAGS'] = '-Wno-error'

    try:
        subprocess.check_call(['make', '-j', str(nb_cores), 'all'])
    except subprocess.CalledProcessError:
        logger.error('Error: binutils compilation failed')
        sys.exit()

    if install:
        cmd = ['make', 'install']
    else:
        cmd = ['make', 'install', f'DESTDIR={INSTALL_DIR}']

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        logger.error('Error: binutils installation failed ')
        sys.exit()


def build_gcc(*args):
    """Build GCC."""

    install, nb_cores, obj_directory, prefix, gcc_directory, target, enable_cxx = args
    languages = 'c'

    if enable_cxx:
        languages += ',c++'

    os.chdir(obj_directory)

    try:
        subprocess.check_call([f'{gcc_directory}/configure',
                               f'--target={target}',
                               f'--prefix={prefix}',
                               f'--program-prefix={target}-',
                               '--with-gnu-as', '--with-gnu-ld', '--disable-nls',
                               '--disable-threads',
                               f'--enable-languages={languages}',
                               '--disable-multilib', '--disable-libgcj',
                               '--without-headers', '--disable-shared', '--enable-lto',
                               '--disable-werror'])
    except subprocess.CalledProcessError:
        logger.error('Error: gcc headers checking failed')
        sys.exit()

    try:
        subprocess.check_call(['make', '-j', str(nb_cores), 'all-gcc'])
    except subprocess.CalledProcessError:
        logger.error('Error: gcc compilation failed')
        sys.exit()

    if install:
        cmd = ['make', 'install-gcc']
    else:
        cmd = ['make', 'install-gcc', f'DESTDIR={INSTALL_DIR}']

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        logger.error('Error: gcc installation failed')
        sys.exit()


def build_gdb(install, nb_cores, gdb_directory, target, prefix):
    """Build GDB."""

    os.chdir(gdb_directory)

    try:
        subprocess.check_call(['./configure',
                               f'--target={target}',
                               f'--prefix={prefix}',
                               f'--program-prefix={target}-',
                               '--enable-werror=no'])
    except subprocess.CalledProcessError:
        logger.error('Error: gdb headers checking failed')
        sys.exit()

    try:
        subprocess.check_call(['make', '-j', str(nb_cores), 'all'])
    except subprocess.CalledProcessError:
        logger.error('Error: gdb compilation failed')
        sys.exit()

    if install:
        cmd = ['make', 'install']
    else:
        cmd = ['make', 'install', f'DESTDIR={INSTALL_DIR}']

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        logger.error('Error: gdb installatior failed')
        sys.exit()


def build_target(platform, install, nb_cores, enable_cxx):
    """Cross-compile gcc toolchain for a given architecture."""

    work_directory = f'{BASEDIR}/{platform}'
    binutils_directory = f'{work_directory}/binutils-{BINUTILS_VERSION}'
    gcc_directory = f'{work_directory}/gcc-{GCC_VERSION}'
    obj_directory = f'{work_directory}/gcc-obj'
    gdb_directory = f'{work_directory}/gdb-{GDB_VERSION}'

    target = set_target_from_platform(platform)

    if os.environ.get('CROSS_PREFIX'):
        cross_prefix = os.environ['CROSS_PREFIX']
    else:
        cross_prefix = '/usr/local/cross/'

    prefix = f'{cross_prefix}{platform}'

    os.environ['PATH'] += f':{INSTALL_DIR}{prefix}/bin'
    os.environ['PATH'] += f':{prefix}/bin'

    cleanup_previous_build(install, prefix, work_directory, obj_directory)
    unpack_tarballs(work_directory)

    build_binutils(install, nb_cores, binutils_directory, target, prefix)
    build_gcc(install, nb_cores, obj_directory, prefix, gcc_directory, target, enable_cxx)
    build_gdb(install, nb_cores, gdb_directory, target, prefix)

    os.chdir(BASEDIR)
    logger.info('>>> Cleaning up')
    cleanup_dir(work_directory)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--arch',
                        help='Target architecture',
                        type=str,
                        choices=['aarch64', 'amd64', 'arm32', 'armhf', 'ia32', 'ia64',
                                 'mips32', 'mips32eb', 'mips64', 'ppc32',
                                 'ppc64', 'sparc32', 'sparc64', 'lm32'],
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

    parser.add_argument('--enable-cxx',
                        help='Build tools for C++ (g++, etc.)',
                        action='store_true')

    arguments = parser.parse_args()

    target_platform = arguments.arch
    install = arguments.install == 'yes'
    nb_cpu_cores = arguments.cores - 1
    enable_cxx=arguments.enable_cxx

    check_headers()
    prepare()
    build_target(target_platform, install, nb_cpu_cores, enable_cxx)

    msg = 'installed' if arguments.install == 'yes' else 'built'
    logger.info(f'>>> Cross-compiler for {target_platform} is now {msg}.')
