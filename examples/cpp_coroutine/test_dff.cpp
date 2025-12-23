// Copyright cocotb contributors
// Licensed under the Revised BSD License, see LICENSE for details.
// SPDX-License-Identifier: BSD-3-Clause

#include <cocotb.h>

using namespace cocotb;

// Clock generator coroutine
task<> Clock(Dut &dut) {
    std::cout << "Starting clock_generator coroutine" << std::endl;
    auto clk = dut["clk"]; // Lookup once
    while (true) {
        clk = 0;
        co_await Timer(5);
        clk = 1;
        co_await Timer(5);
    }
}


COCOTB_TEST(test_dff)  // registers the test
task<> test_dff(Dut &dut) {
    std::cout << "Starting test_dff coroutine" << std::endl;

    // Set initial input value to prevent it from floating
    dut["d"] = 0;

    // Create a 10us period clock driver on port `clk`
    auto clock = Clock(dut);

    // Start the clock
    auto clk = start_soon(clock);

    // Synchronize with the clock. This will register the initial `d` value
    co_await RisingEdge(dut["clk"]);

    auto expected_val = 0;  // Matches initial input value
    for (int i = 0; i < 100; ++i) {
        auto val = rand() % 2;
        dut["d"] = val;  // Assign the random value val to the input port d
        co_await RisingEdge(dut["clk"]);
        auto q_val = dut["q"].value<int>();
        if (expected_val != q_val)
            throw std::runtime_error("output q was incorrect on the " + std::to_string(i) + " th cycle");
        expected_val = val;  // Save random value for next RisingEdge
    }

    co_await RisingEdge(dut["clk"]);
    if (expected_val != dut["q"].value<int>())
        throw std::runtime_error("output q was incorrect on the last cycle");

    std::cout << "test_dff completed successfully" << std::endl;
}


task<> Wait(Dut &dut, int time) {
    co_await Timer(time);
    dut["d"] = 1;
    dut["clk"] = 1;
}

COCOTB_TEST(test_dff_post)
task<> test_dff_post(Dut &dut) {
    cocotb::log.info("Starting test_dff_post coroutine");

    dut["d"] = 0;
    dut["clk"] = 0;

    auto wait = start_soon(Wait(dut, 100));
    co_await wait.join();

    co_await Timer(10);
    if (1 != dut["d"].value<int>())
        throw std::runtime_error("output d was incorrect");

    cocotb::log.info("Completed test_dff_post successfully");
}