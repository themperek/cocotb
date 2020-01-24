# Copyright cocotb contributors
# Licensed under the Revised BSD License, see LICENSE for details.
# SPDX-License-Identifier: BSD-3-Clause

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


def get_ext_filename_without_platform_suffix(filename):
    name, ext = os.path.splitext(filename)
    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX")

    if ext_suffix == ext:
        return filename

    ext_suffix = ext_suffix.replace(ext, "")
    idx = name.find(ext_suffix)

    if idx == -1:
        return filename
    else:
        return name[:idx] + ext


class build_ext(_build_ext):

    # Needed for Windows to not assume python module (generate interface in def file)
    def get_export_symbols(self, ext):
        return None

    # For proper library name, based on https://github.com/cython/cython/issues/1740
    def get_ext_filename(self, ext_name):
        filename = super().get_ext_filename(ext_name)

        filename_short = get_ext_filename_without_platform_suffix(filename)

        # icarus requires vpl extenasion
        if filename.find("icarus") >= 0:
            filename_short = filename_short.replace("libvpi.so", "gpivpi.vpl")

        return filename_short


def _extra_link_args(lib_name):
    if sys.platform == "darwin":
        return ["-Wl,-install_name,@loader_path/%s.so" % lib_name]
    else:
        return []


def _get_common_lib_ext(build_dir, include_dir, share_lib_dir, dist):

    if sys.platform == "darwin":
        ld_library = sysconfig.get_config_var("LIBRARY")
    else:
        ld_library = sysconfig.get_config_var("LDLIBRARY")

    if ld_library is not None:
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
        extra_link_args=_extra_link_args("libcocotbutils"),
    )

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
        extra_link_args=_extra_link_args("libgpilog"),
    )

    #
    #  libcocotb
    #
    libcocotb = Extension(
        "libcocotb",
        define_macros=[("PYTHON_SO_LIB", python_lib)],
        include_dirs=[include_dir],
        library_dirs=[build_dir],
        libraries=["gpilog", "cocotbutils"],
        sources=[os.path.join(share_lib_dir, "embed", "gpi_embed.c")],
        extra_link_args=_extra_link_args("libcocotb"),
    )

    #
    #  libgpi
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
        extra_link_args=_extra_link_args("libgpi"),
    )

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

    return [libcocotbutils, libgpilog, libcocotb, libgpi, libsim]


def _get_vpi_lib_ext(
    build_dir,
    include_dir,
    share_lib_dir,
    dist,
    sim_define,
    extra_lib=[],
    extra_lib_dir=[],
):
    libvpi = Extension(
        sim_define.lower() + "/libvpi",
        define_macros=[("VPI_CHECKING", "1")] + [(sim_define, "")],
        include_dirs=[include_dir],
        libraries=["gpi", "gpilog"] + extra_lib,
        library_dirs=[build_dir] + extra_lib_dir,
        sources=[
            os.path.join(share_lib_dir, "vpi", "VpiImpl.cpp"),
            os.path.join(share_lib_dir, "vpi", "VpiCbHdl.cpp"),
        ],
        extra_link_args=["-Wl,-rpath,$ORIGIN/.."],
    )

    return libvpi


def _get_vhpi_lib_ext(
    build_dir,
    include_dir,
    share_lib_dir,
    dist,
    sim_define,
    extra_lib=[],
    extra_lib_dir=[],
):
    libcocotbvhpi = Extension(
        sim_define.lower() + "/libcocotbvhpi",
        include_dirs=[include_dir],
        define_macros=[("VHPI_CHECKING", 1)] + [(sim_define, "")],
        libraries=["gpi", "gpilog", "stdc++"] + extra_lib,
        library_dirs=[build_dir] + extra_lib_dir,
        sources=[
            os.path.join(share_lib_dir, "vhpi", "VhpiImpl.cpp"),
            os.path.join(share_lib_dir, "vhpi", "VhpiCbHdl.cpp"),
        ],
        extra_link_args=["-Wl,-rpath,$ORIGIN/.."],
    )

    return libcocotbvhpi


def build(build_dir, debug=False):

    logger = logging.getLogger(__name__)

    if debug:
        distutils.log.set_verbosity(distutils.log.DEBUG)
    else:
        distutils.log.set_verbosity(0)  # Disable logging compilation commands

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

    ext = _get_common_lib_ext(build_dir, include_dir, share_lib_dir, dist)

    #
    #  Icarus Verilog
    #
    icarus_compile = True
    icarus_extra_lib = []
    icarus_extra_lib_path = []
    if os.name == "nt":
        iverilog_path = find_executable("iverilog")
        if iverilog_path is None:
            logger.warning(
                "Icarus Verilog executable not found. No VPI interface will be available."
            )
            icarus_compile = False
        else:
            icarus_path = os.path.dirname(os.path.dirname(iverilog_path))
            icarus_extra_lib = ["vpi"]
            icarus_extra_lib_path = [os.path.join(icarus_path, "lib")]

    if icarus_compile:
        icarus_vpi_ext = _get_vpi_lib_ext(
            build_dir=build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="ICARUS",
            extra_lib=icarus_extra_lib,
            extra_lib_dir=icarus_extra_lib_path,
        )

        ext.append(icarus_vpi_ext)

    logger.warning("Compiling interface libraries for cocotb ...")

    #
    #  Modelsim/Questa
    #
    vsim_path = find_executable("vdbg")
    modelsim_compile = True
    modelsim_extra_lib = []
    modelsim_extra_lib_path = []
    if os.name == "nt":
        if vsim_path is None:
            logger.warning(
                "Modelsim/Questa executable (vdbg) not found. No VPI interface will be available."
            )
            modelsim_compile = False
        else:
            modelsim_bin_dir = os.path.dirname(vsim_path)
            modelsim_extra_lib = ["mtipli"]
            modelsim_extra_lib_path = [modelsim_bin_dir]

    if modelsim_compile:
        modelsim_vpi_ext = _get_vpi_lib_ext(
            build_dir=build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="MODELSIM",
            extra_lib=modelsim_extra_lib,
            extra_lib_dir=modelsim_extra_lib_path,
        )

        ext.append(modelsim_vpi_ext)

    if vsim_path is None:
        logger.warning(
            "Modelsim/Questa executable (vdbg) executable not found. No FLI interface will be available."
        )
    else:
        modelsim_dir = os.path.dirname(os.path.dirname(vsim_path))
        modelsim_include_dir = os.path.join(modelsim_dir, "include")
        if os.path.isfile(os.path.join(modelsim_include_dir, "mti.h")):
            fli_ext = Extension(
                "libfli",
                include_dirs=[include_dir, modelsim_include_dir],
                libraries=["gpi", "gpilog", "stdc++"] + modelsim_extra_lib,
                library_dirs=[build_dir] + modelsim_extra_lib_path,
                sources=[
                    os.path.join(share_lib_dir, "fli", "FliImpl.cpp"),
                    os.path.join(share_lib_dir, "fli", "FliCbHdl.cpp"),
                    os.path.join(share_lib_dir, "fli", "FliObjHdl.cpp"),
                ],
                extra_link_args=["-Wl,-rpath,$ORIGIN"],
            )

            ext.append(fli_ext)

        else:
            logger.warning(
                "Building FLI interface for Modelsim failed! No mti.h available."
            )  # some Modelsim version does not include FLI.

    #
    # GHDL
    #
    if os.name == "posix":
        ghdl_vpi_ext = _get_vpi_lib_ext(
            build_dir=build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="GHDL",
        )
        ext.append(ghdl_vpi_ext)

    #
    # IUS
    #
    if os.name == "posix":
        ius_vpi_ext = _get_vpi_lib_ext(
            build_dir=build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="IUS",
        )
        ext.append(ius_vpi_ext)

        ius_vhpi_ext = _get_vhpi_lib_ext(
            build_dir=build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="IUS",
        )
        ext.append(ius_vhpi_ext)

    #
    # VCS
    #
    if os.name == "posix":
        vcs_vpi_ext = _get_vpi_lib_ext(
            build_dir=build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="VCS",
        )
        ext.append(vcs_vpi_ext)

    #
    # Aldec
    #
    vsimsa_path = find_executable("vsimsa")
    if vsimsa_path is None:
        logger.warning(
            "Riviera executable (vsimsa) not found. No VPI/VHPI interface will be available."
        )
    else:
        aldec_path = os.path.dirname(vsimsa_path)
        aldec_extra_lib = ["aldecpli"]
        aldec_extra_lib_path = [aldec_path]

        aldec_vpi_ext = _get_vpi_lib_ext(
            build_dir=build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="ALDEC",
            extra_lib=aldec_extra_lib,
            extra_lib_dir=aldec_extra_lib_path,
        )
        ext.append(aldec_vpi_ext)

        aldec_vhpi_ext = _get_vhpi_lib_ext(
            build_dir=build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="ALDEC",
            extra_lib=aldec_extra_lib,
            extra_lib_dir=aldec_extra_lib_path,
        )
        ext.append(aldec_vhpi_ext)

    #
    # Verilator
    #
    if os.name == "posix":
        verilator_vpi_ext = _get_vpi_lib_ext(
            build_dir=build_dir,
            include_dir=include_dir,
            share_lib_dir=share_lib_dir,
            dist=dist,
            sim_define="VERILATOR",
        )
        ext.append(verilator_vpi_ext)

    dist.ext_modules = ext
    _build_ext = build_ext(dist)
    _build_ext.build_lib = build_dir
    _build_ext.finalize_options()
    _build_ext.run()
