# Copyright cocotb contributors
# Licensed under the Revised BSD License, see LICENSE for details.
# SPDX-License-Identifier: BSD-3-Clause

import subprocess
import os
import sys
import tempfile
import shutil
from xml.etree import cElementTree as ET
from distutils.sysconfig import get_config_var

__tracebackhide__  = True  # not show up in the traceback in pytest

class Simulator(object):
    def __init__(
        self,
        toplevel,
        module,
        work_dir=None,
        python_search=None,
        toplevel_lang="verilog",
        verilog_sources=None,
        vhdl_sources=None,
        includes=None,
        defines=None,
        compile_args=None,
        simulation_args=None,
        extra_args=None,
        plus_args=None,
        force_compile=False,
        testcase=None,
        sim_build="sim_build",
        seed=None,
        extra_env=None,
        compile_only=False,
        gui=False,
        **kwargs
    ):

        self.sim_dir = os.path.join(os.getcwd(), sim_build)
        if not os.path.exists(self.sim_dir):
            os.makedirs(self.sim_dir)

        self.lib_dir = os.path.join(os.path.dirname(__file__), "libs")

        self.lib_ext = "so"
        if os.name == "nt":
            self.lib_ext = "dll"

        self.module = module  # TODO: Auto discovery, try introspect ?

        self.work_dir = self.sim_dir

        if work_dir is not None:
            absworkdir = os.path.abspath(work_dir)
            if os.path.isdir(absworkdir):
                self.work_dir = absworkdir

        if python_search is None:
            python_search = []

        self.python_search = python_search

        self.toplevel = toplevel
        self.toplevel_lang = toplevel_lang

        if verilog_sources is None:
            verilog_sources = []

        self.verilog_sources = self.get_abs_paths(verilog_sources)

        if vhdl_sources is None:
            vhdl_sources = []

        self.vhdl_sources = self.get_abs_paths(vhdl_sources)

        if includes is None:
            includes = []

        self.includes = self.get_abs_paths(includes)

        if defines is None:
            defines = []

        self.defines = defines

        if compile_args is None:
            compile_args = []

        if extra_args is None:
            extra_args = []

        self.compile_args = compile_args + extra_args

        if simulation_args is None:
            simulation_args = []

        self.simulation_args = simulation_args + extra_args

        if plus_args is None:
            plus_args = []

        self.plus_args = plus_args
        self.force_compile = force_compile
        self.compile_only = compile_only

        for arg in kwargs:
            setattr(self, arg, kwargs[arg])

        if extra_env is not None:
            self.env = extra_env
        else:
            self.env = {}

        if testcase is not None:
            self.env["TESTCASE"] = testcase

        if seed is not None:
            self.env["RANDOM_SEED"] = str(seed)

        self.gui = gui

    def _set_env(self):

        for e in os.environ:
            self.env[e] = os.environ[e]

        self.env["PATH"] += os.pathsep + self.lib_dir

        self.env["PYTHONPATH"] = os.pathsep.join(sys.path)

        for path in self.python_search:
            self.env["PYTHONPATH"] += os.pathsep + path

        self.env["PYTHONHOME"] = get_config_var("prefix")

        self.env["TOPLEVEL"] = self.toplevel
        self.env["COCOTB_SIM"] = "1"
        self.env["MODULE"] = self.module

        if not os.path.exists(self.sim_dir):
            os.makedirs(self.sim_dir)

    def build_command(self):
        raise NotImplementedError()

    def run(self):

        sys.tracebacklimit = 0  # remove not needed traceback from assert

        # use temporary results file
        if not os.getenv("COCOTB_RESULTS_FILE"):
            tmp_results_file = tempfile.NamedTemporaryFile(
                prefix=self.sim_dir + os.path.sep, suffix="_results.xml"
            )
            results_xml_file = tmp_results_file.name
            tmp_results_file.close()
            self.env["COCOTB_RESULTS_FILE"] = results_xml_file
        else:
            results_xml_file = os.getenv("COCOTB_RESULTS_FILE")

        cmds = self.build_command()
        self._set_env()
        self.execute(cmds)

        if not self.compile_only:
            results_file_exist = os.path.isfile(results_xml_file)
            assert (
                results_file_exist
            ), "Simulation terminated abnormally. Results file not found."

            tree = ET.parse(results_xml_file)
            for ts in tree.iter("testsuite"):
                for tc in ts.iter("testcase"):
                    for failure in tc.iter("failure"):
                        assert False, '{} class="{}" test="{}" error={}'.format(
                            failure.get("message"),
                            tc.get("classname"),
                            tc.get("name"),
                            failure.get("stdout"),
                        )

        print("Results file: %s" % results_xml_file)
        return results_xml_file

    def get_abs_paths(self, paths):
        paths_abs = []
        for path in paths:
            if os.path.isabs(path):
                paths_abs.append(os.path.abspath(path))
            else:
                paths_abs.append(os.path.abspath(os.path.join(os.getcwd(), path)))

        return paths_abs

    def execute(self, cmds):

        for cmd in cmds:
            print("Running command: " + " ".join(cmd))

            # TODO: create at thread to handle stderr and log as error?
            # TODO: log forwarding

            process = subprocess.run(cmd, cwd=self.work_dir, env=self.env)

            if process.returncode != 0:
                raise RuntimeError(
                    "Process '%s' termindated with error %d"
                    % (process.args[0], process.returncode)
                )

    def outdated(self, output, dependencies):

        if not os.path.isfile(output):
            return True

        output_mtime = os.path.getmtime(output)

        dep_mtime = 0
        for file in dependencies:
            mtime = os.path.getmtime(file)
            if mtime > dep_mtime:
                dep_mtime = mtime

        if dep_mtime > output_mtime:
            return True

        return False


class Icarus(Simulator):
    def __init__(self, *argv, **kwargs):
        super(Icarus, self).__init__(*argv, **kwargs)

        if self.vhdl_sources:
            raise ValueError("This simulator does not support VHDL")

        self.sim_file = os.path.join(self.sim_dir, self.toplevel + ".vvp")

    def get_include_commands(self, includes):
        include_cmd = []
        for dir in includes:
            include_cmd.append("-I")
            include_cmd.append(dir)

        return include_cmd

    def get_define_commands(self, defines):
        defines_cmd = []
        for define in defines:
            defines_cmd.append("-D")
            defines_cmd.append(define)

        return defines_cmd

    def compile_command(self):

        cmd_compile = (
            ["iverilog", "-o", self.sim_file, "-s", self.toplevel, "-g2012"]
            + self.get_define_commands(self.defines)
            + self.get_include_commands(self.includes)
            + self.compile_args
            + self.verilog_sources
        )

        return cmd_compile

    def run_command(self):
        return (
            ["vvp", "-M", self.lib_dir, "-m", "libcocotbvpi_icarus"]
            + self.simulation_args
            + [self.sim_file]
            + self.plus_args
        )

    def build_command(self):
        cmd = []
        if self.outdated(self.sim_file, self.verilog_sources) or self.force_compile:
            cmd.append(self.compile_command())
        else:
            print("Skipping compilation:" + self.sim_file)

        # TODO: check dependency?
        if not self.compile_only:
            cmd.append(self.run_command())

        return cmd


def run(simulator=None, **kwargs):

    sim_env = os.getenv("SIM", "icarus")

    supported_sim = ["icarus", "questa", "ius", "vcs", "ghdl", "aldec", "verilator"]
    if (sim_env in supported_sim) or simulator:
        pass
    else:
        raise NotImplementedError(
            "Set SIM/sim variable. Supported: " + ", ".join(supported_sim)
        )

    if simulator:
        sim = simulator(**kwargs)
    elif sim_env == "icarus":
        sim = Icarus(**kwargs)
    # elif sim_env == "questa":
    #     sim = Questa(**kwargs)
    # elif sim_env == "ius":
    #     sim = Ius(**kwargs)
    # elif sim_env == "vcs":
    #     sim = Vcs(**kwargs)
    # elif sim_env == "ghdl":
    #     sim = Ghdl(**kwargs)
    # elif sim_env == "aldec":
    #     sim = Aldec(**kwargs)
    # elif sim_env == "verilator":
    #     sim = Verilator(**kwargs)

    return sim.run()


def clean(recursive=False):
    dir = os.getcwd()

    def rm_clean():
        sim_build_dir = os.path.join(dir, "sim_build")
        if os.path.isdir(sim_build_dir):
            print("Removing:", sim_build_dir)
            shutil.rmtree(sim_build_dir, ignore_errors=True)

    rm_clean()

    if recursive:
        for dir, subFolders, files in os.walk(dir):
            rm_clean()
