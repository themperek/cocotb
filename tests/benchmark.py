# Copyright cocotb contributors
# Licensed under the Revised BSD License, see LICENSE for details.
# SPDX-License-Identifier: BSD-3-Clause

from pathlib import Path

from cocotb.runner import get_runner


def build_and_run_matrix_multiplier(benchmark, sim):

    toplevel_lang = "verilog"
    extra_args = []

    if sim == "ghdl":
        extra_args = ["--std=08"]
        toplevel_lang = "vhdl"

    verilog_sources = []
    vhdl_sources = []

    proj_path = (
        Path(__file__).resolve().parent.parent / "examples" / "matrix_multiplier"
    )

    if toplevel_lang == "verilog":
        verilog_sources = [proj_path / "hdl" / "matrix_multiplier.sv"]
    else:
        vhdl_sources = [
            proj_path / "hdl" / "matrix_multiplier_pkg.vhd",
            proj_path / "hdl" / "matrix_multiplier.vhd",
        ]

    runner = get_runner(sim)()

    runner.build(
        toplevel="matrix_multiplier",
        verilog_sources=verilog_sources,
        vhdl_sources=vhdl_sources,
        extra_args=extra_args,
    )

    @benchmark
    def run_test():
        runner.test(
            toplevel="matrix_multiplier",
            toplevel_lang=toplevel_lang,
            py_module="test_matrix_multiplier",
            extra_args=extra_args,
            python_search=[proj_path / "tests"],
        )


def test_matrix_multiplier_icarus(benchmark):
    build_and_run_matrix_multiplier(benchmark, "icarus")


# def test_matrix_multiplier_ghdl(benchmark):
#     build_and_run_matrix_multiplier(benchmark, "ghdl")
