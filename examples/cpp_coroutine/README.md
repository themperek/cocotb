# C++ Coroutine Testbench Example

This example demonstrates how to use the C++ coroutine interface for cocotb.

## Building

To build this example, you need:

1. A C++20 compatible compiler (GCC 10+, Clang 10+, or MSVC 2019+)
2. CMake (version 3.15 or later)

# Build and run example:

```bash
make
```

This will create `libcocotb_cpp_example.so` in the `sim_build` directory.

The library can be loaded via the `GPI_USERS` environment variable when running a simulation:

```bash
export GPI_USERS=/path/to/sim_build/libcocotb_cpp_example.so,cocotb_entry_point
```
