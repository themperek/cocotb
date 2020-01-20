# Copyright (c) cocotb contributors
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the copyright holder nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL POTENTIAL VENTURES LTD BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import sys
import sysconfig
import errno
import distutils
import shutil
import logging

from setuptools import Extension
from setuptools.dist import Distribution
from distutils.spawn import find_executable
from setuptools.command.build_ext import build_ext as _build_ext


# Needed for Windows to not assume python module (generate interface in def file)
class build_ext(_build_ext):
    def get_export_symbols(self, ext):
        return None


def _rename_safe(target, link_name):
    """Rename or symlink on Mac or copy on Windows."""

    if sys.platform == "darwin":  # On Mac there is an issue with rename? Workaround!
        try:
            os.symlink(target, link_name)
        except OSError as e:
            if e.errno == errno.EEXIST:
                os.remove(link_name)
                os.symlink(target, link_name)
            else:
                raise e
        return

    if (
        os.name == "nt"
    ):  # On Windows there is an issue with symlink and rename? !Workaround!
        shutil.copy2(target, link_name)
        return

    try:
        os.rename(target, link_name)
    except OSError as e:
        if e.errno == errno.EEXIST:
            os.remove(link_name)
            os.rename(target, link_name)
        else:
            raise e


def _build_lib(lib, dist, build_dir):
    """Use setuptools to build *lib* into *build_dir*."""

    dist.ext_modules = [lib]

    _build_ext = build_ext(dist)
    _build_ext.build_lib = build_dir
    _build_ext.build_temp = build_dir

    _build_ext.finalize_options()

    _build_ext.run()
    out_lib = _build_ext.get_outputs()

    lib_name = lib.name
    lib_path = os.path.abspath(out_lib[0])
    dir_name = os.path.dirname(lib_path)
    ext_name = os.path.splitext(lib_path)[1][1:]
    if os.name == "nt":
        ext_name = "dll"

    target = os.path.join(os.path.abspath(dir_name), lib_name + "." + ext_name)
    if target != lib_path:
        _rename_safe(
            lib_path, os.path.join(os.path.abspath(dir_name), lib_name + "." + ext_name)
        )

    return lib_name + "." + ext_name


def _extra_link_args(lib_name):
    if sys.platform == "darwin":
        return ["-Wl,-install_name,@loader_path/%s.so" % lib_name]
    else:
        return []


def build_common_libs(build_dir, include_dir, share_lib_dir, dist):

    if sys.platform == "darwin":
        ld_library = sysconfig.get_config_var("LIBRARY")
    else:
        ld_library = sysconfig.get_config_var("LDLIBRARY")

    if ld_library:
        python_lib_link = os.path.splitext(ld_library)[0][3:]
    else:
        python_version = sysconfig.get_python_version().replace(".", "")
        python_lib_link = "python" + python_version

    if os.name == "nt":
        ext_name = "dll"
        python_lib = python_lib_link + "." + ext_name
    else:
        ext_name = "so"
        python_lib = "lib" + python_lib_link + "." + ext_name

    #
    #  libcocotbutils
    #
    libcocotbutils = Extension(
        "libcocotbutils",
        include_dirs=[include_dir],
        sources=[os.path.join(share_lib_dir, "utils", "cocotb_utils.c")],
        extra_link_args=_extra_link_args("libcocotbutils")
    )

    _build_lib(libcocotbutils, dist, build_dir)

    #
    #  libgpilog
    #
    gpilog_library_dirs = [build_dir]
    if sys.platform == "darwin":
        gpilog_library_dirs = [build_dir, sysconfig.get_config_var("LIBDIR")]

    libgpilog = Extension(
        "libgpilog",
        include_dirs=[include_dir],
        libraries=[python_lib_link, "pthread", "m", "cocotbutils"],
        library_dirs=gpilog_library_dirs,
        sources=[os.path.join(share_lib_dir, "gpi_log", "gpi_logging.c")],
        extra_link_args=_extra_link_args("libgpilog")
    )

    _build_lib(libgpilog, dist, build_dir)

    #
    #  libgpilog
    #
    libcocotb = Extension(
        "libcocotb",
        define_macros=[("PYTHON_SO_LIB", python_lib)],
        include_dirs=[include_dir],
        library_dirs=[build_dir],
        libraries=["gpilog", "cocotbutils"],
        sources=[os.path.join(share_lib_dir, "embed", "gpi_embed.c")],
        extra_link_args=_extra_link_args("libcocotb")
    )

    _build_lib(libcocotb, dist, build_dir)

    #
    #  libgpilog
    #
    libgpi = Extension(
        "libgpi",
        define_macros=[("LIB_EXT", ext_name), ("SINGLETON_HANDLES", "")],
        include_dirs=[include_dir],
        libraries=["cocotbutils", "gpilog", "cocotb", "stdc++"],
        library_dirs=[build_dir],
        sources=[
            os.path.join(share_lib_dir, "gpi", "GpiCbHdl.cpp"),
            os.path.join(share_lib_dir, "gpi", "GpiCommon.cpp"),
        ],
        extra_link_args=_extra_link_args("libgpi")
    )

    _build_lib(libgpi, dist, build_dir)

    #
    #  simulator
    #
    libsim = Extension(
        "simulator",
        include_dirs=[include_dir],
        libraries=["cocotbutils", "gpilog", "gpi"],
        library_dirs=[build_dir],
        sources=[os.path.join(share_lib_dir, "simulator", "simulatormodule.c")],
    )

    _build_lib(libsim, dist, build_dir)


def build_vpi_lib(
    build_dir,
    include_dir,
    share_lib_dir,
    dist,
    sim_define,
    extra_lib=[],
    extra_lib_dir=[],
):
    libvpi = Extension(
        "libvpi",
        define_macros=[("VPI_CHECKING", "1")] + [(sim_define, "")],
        include_dirs=[include_dir],
        libraries=["gpi", "gpilog"] + extra_lib,
        library_dirs=[build_dir] + extra_lib_dir,
        sources=[
            os.path.join(share_lib_dir, "vpi", "VpiImpl.cpp"),
            os.path.join(share_lib_dir, "vpi", "VpiCbHdl.cpp"),
        ],
        extra_link_args=["-Wl,-rpath,$ORIGIN"],
    )
    return _build_lib(libvpi, dist, build_dir)


def build_vhpi_lib(
    build_dir,
    include_dir,
    share_lib_dir,
    dist,
    sim_define,
    extra_lib=[],
    extra_lib_dir=[],
):
    libcocotbvhpi = Extension(
        "libcocotbvhpi",
        include_dirs=[include_dir],
        define_macros=[("VHPI_CHECKING", 1)] + [(sim_define, "")],
        libraries=["gpi", "gpilog", "stdc++"] + extra_lib,
        library_dirs=[build_dir] + extra_lib_dir,
        sources=[
            os.path.join(share_lib_dir, "vhpi", "VhpiImpl.cpp"),
            os.path.join(share_lib_dir, "vhpi", "VhpiCbHdl.cpp"),
        ],
        extra_link_args=["-Wl,-rpath,$ORIGIN"],
    )

    return _build_lib(libcocotbvhpi, dist, build_dir)


def build(build_dir):

    logger = logging.getLogger(__name__)

    distutils.log.set_verbosity(0)  # Disable logging comiliation commands in disutils
    # distutils.log.set_verbosity(distutils.log.DEBUG) # Set DEBUG level

    cfg_vars = distutils.sysconfig.get_config_vars()
    for key, value in cfg_vars.items():
        if type(value) == str:
            cfg_vars[key] = value.replace("-Wstrict-prototypes", "")

    if sys.platform == "darwin":
        cfg_vars["LDSHARED"] = cfg_vars["LDSHARED"].replace("-bundle", "-dynamiclib")

    share_dir = os.path.join(os.path.dirname(__file__), "share")
    share_lib_dir = os.path.join(share_dir, "lib")
    build_dir = os.path.abspath(build_dir)
    include_dir = os.path.join(share_dir, "include")

    dist = Distribution()
    dist.parse_config_files()

    #
    #  Icarus Verilog
    #
    logger.warning("Compiling interface libraries for Icarus Verilog ...")
    icarus_build_dir = os.path.join(build_dir, "icarus")
    icarus_compile = True
    icarus_extra_lib = []
    icarus_extra_lib_path = []
    if os.name == "nt":
        iverilog_path = find_executable("iverilog")
        if iverilog_path is None:
            logger.warning(
                "Icarus Verilog executable not found. VPI interface will be available."
            )
            icarus_compile = False
        else:
            icarus_path = os.path.dirname(os.path.dirname(iverilog_path))
            icarus_extra_lib = ["vpi"]
            icarus_extra_lib_path = [os.path.join(icarus_path, "lib")]

    if icarus_compile:
        build_common_libs(icarus_build_dir, include_dir, share_lib_dir, dist)
        icarus_vpi_lib_name = build_vpi_lib(
            build_dir=icarus_build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="ICARUS",
            extra_lib=icarus_extra_lib,
            extra_lib_dir=icarus_extra_lib_path,
        )

        _rename_safe(
            os.path.join(icarus_build_dir, icarus_vpi_lib_name),
            os.path.join(icarus_build_dir, "gpivpi.vpl"),
        )

    #
    #  Modelsim/Questa
    #
    logger.warning("Compiling interface libraries for Modelsim/Questa ...")
    vsim_path = find_executable("vopt")
    modelsim_build_dir = os.path.join(build_dir, "modelsi")
    modelsim_compile = True
    modelsim_extra_lib = []
    modelsim_extra_lib_path = []

    if os.name == "nt":
        if vsim_path is None:
            logger.warning(
                "Modelsim/Questa executable (vopt) not found. VPI interface will be available."
            )
            modelsim_compile = False
        else:
            modelsim_bin_dir = os.path.dirname(vsim_path)
            modelsim_extra_lib = ["mtipli"]
            modelsim_extra_lib_path = [modelsim_bin_dir]

    if modelsim_compile:
        build_common_libs(modelsim_build_dir, include_dir, share_lib_dir, dist)

        build_vpi_lib(
            build_dir=modelsim_build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="MODELSIM",
            extra_lib=modelsim_extra_lib,
            extra_lib_dir=modelsim_extra_lib_path,
        )

    if vsim_path is None:
        logger.warning(
            "Modelsim/Questa executable (vopt) executable not found. FLI interface will be available."
        )
    else:
        modelsim_dir = os.path.dirname(os.path.dirname(vsim_path))
        libfli = Extension(
            "libfli",
            include_dirs=[include_dir, os.path.join(modelsim_dir, "include")],
            libraries=["gpi", "gpilog", "stdc++"] + modelsim_extra_lib,
            library_dirs=[modelsim_build_dir] + modelsim_extra_lib_path,
            sources=[
                os.path.join(share_lib_dir, "fli", "FliImpl.cpp"),
                os.path.join(share_lib_dir, "fli", "FliCbHdl.cpp"),
                os.path.join(share_lib_dir, "fli", "FliObjHdl.cpp"),
            ],
            extra_link_args=["-Wl,-rpath,$ORIGIN"],
        )

        try:
            _build_lib(libfli, dist, modelsim_build_dir)
        except:  # noqa: E722
            logger.warning(
                "Building FLI intercae for Modelsim faild!"
            )  # some Modelsim version doesn not include FLI?

    #
    # GHDL
    #
    if os.name == "posix":
        logger.warning("Compiling interface libraries for GHDL ...")
        ghdl_build_dir = os.path.join(build_dir, "ghdl")

        build_common_libs(ghdl_build_dir, include_dir, share_lib_dir, dist)

        build_vpi_lib(
            build_dir=ghdl_build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="GHDL",
        )

    #
    # IUS
    #
    if os.name == "posix":
        logger.warning("Compiling interface libraries for IUS ...")
        ius_build_dir = os.path.join(build_dir, "ius")

        build_common_libs(ius_build_dir, include_dir, share_lib_dir, dist)

        build_vpi_lib(
            build_dir=ius_build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="IUS",
        )

        build_vhpi_lib(
            build_dir=ius_build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="IUS",
        )

    #
    # VCS
    #
    if os.name == "posix":
        logger.warning("Compiling interface libraries for VCS ...")
        vcs_build_dir = os.path.join(build_dir, "vcs")

        build_common_libs(vcs_build_dir, include_dir, share_lib_dir, dist)

        build_vpi_lib(
            build_dir=vcs_build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="VCS",
        )

    #
    # Aldec
    #
    vsimsa_path = find_executable("vsimsa")
    if vsimsa_path is None:
        logger.warning(
            "Riviera executable not found. No VPI/VHPI interface will be available."
        )
    else:
        logger.warning("Compiling interface libraries for Aldec ...")
        aldec_build_dir = os.path.join(build_dir, "aldec")
        aldec_path = os.path.dirname(vsimsa_path)
        aldec_extra_lib = ["aldecpli"]
        aldec_extra_lib_path = [aldec_path]

        build_common_libs(aldec_build_dir, include_dir, share_lib_dir, dist)

        build_vpi_lib(
            build_dir=aldec_build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="ALDEC",
            extra_lib=aldec_extra_lib,
            extra_lib_dir=aldec_extra_lib_path,
        )

        build_vhpi_lib(
            build_dir=aldec_build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="ALDEC",
            extra_lib=aldec_extra_lib,
            extra_lib_dir=aldec_extra_lib_path,
        )

    #
    # Verilator
    #
    if os.name == "posix":
        logger.warning("Compiling interface libraries for Verilator ...")
        vcs_build_dir = os.path.join(build_dir, "verilator")

        build_common_libs(vcs_build_dir, include_dir, share_lib_dir, dist)

        build_vpi_lib(
            build_dir=vcs_build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="VERILATOR",
        )

    return
