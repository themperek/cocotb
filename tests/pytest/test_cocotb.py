import os
import pytest
from cocotb.run import run
from cocotb.run import Icarus

tests_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.skipif(os.getenv("SIM") == "ghdl", reason="Verilog not suported")
@pytest.mark.parametrize(
    "module_name",
    [
        "test_deprecated",
        "test_doctests",
        "test_synchronization_primitives",
        "test_concurrency_primitives",
        "test_tests",
        "test_generator_coroutines",
        "test_timing_triggers",
        "test_scheduler",
        "test_clock",
        "test_edge_triggers",
        "test_async_coroutines",
        "test_handle",
        "test_logging",
    ],
)
def test_cocotb(module_name):
    run(
        verilog_sources=[
            os.path.join(tests_dir, "designs", "sample_module", "sample_module.sv")
        ],
        python_search=[os.path.join(tests_dir, "test_cases", "test_cocotb")],
        toplevel="sample_module",
        module=module_name,
    )


class IcarusCustom(Icarus):
    def run_command(self):
        return super().run_command() + ["-v", "-l", self.logfile]


@pytest.mark.skipif(os.getenv("SIM", "icarus") != "icarus", reason="Custom for Icarus")
def test_cocotb_custom_icarus():
    IcarusCustom(
        verilog_sources=[
            os.path.join(tests_dir, "designs", "sample_module", "sample_module.sv")
        ],
        python_search=[os.path.join(tests_dir, "test_cases", "test_cocotb")],
        toplevel="sample_module",
        module="test_clock",
        logfile="custom_log.log",  # extra custom argument
    ).run()


if __name__ == "__main__":
    test_cocotb(module_name="test_clock")
    # test_cocotb_custom_icarus()
