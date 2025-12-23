# CMakeLists.txt for C++ coroutine example
cmake_minimum_required(VERSION 3.15)
project(cocotb_cpp_example)

# Require C++20 for coroutines
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find cocotb GPI include directory
# This assumes cocotb is installed or the source is available
set(COCOTB_INCLUDE_DIR "${CMAKE_SOURCE_DIR}/../../src/cocotb/share/include")
set(COCOTB_LIB_DIR "${CMAKE_SOURCE_DIR}/../../src/cocotb/share/lib")

include_directories(".")

# Include directories
include_directories(${COCOTB_INCLUDE_DIR})

# Source files
set(SOURCES
    test_dff.cpp
)

# Build as a shared library that can be loaded via GPI_USERS
add_library(cocotb_cpp_example SHARED ${SOURCES})
set_target_properties(cocotb_cpp_example PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    OUTPUT_NAME "cocotb_cpp_example"
)

# Compiler flags
target_compile_options(cocotb_cpp_example PRIVATE
    -Wall
    -Wextra
    -Wpedantic
)

# Note: The GPI functions will be resolved at runtime when the library
# is loaded by the simulator via GPI_USERS. No linking is needed at build time.


