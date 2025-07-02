# Migration from distutils to CMake with scikit-build-core

This document describes the migration of cocotb's build system from `distutils` to `CMake` using `scikit-build-core`.

## Overview

The cocotb project has been migrated from a custom `distutils`-based build system to a modern `CMake`-based build system using `scikit-build-core`. This migration provides several benefits while maintaining full compatibility with the existing build requirements.

## Benefits of the Migration

1. **Modern Build System**: CMake is a more modern and widely-adopted build system with better cross-platform support
2. **Better Windows Support**: CMake handles Windows-specific compilation complexities more elegantly
3. **Improved Dependency Management**: Better handling of library dependencies and linking
4. **Parallel Builds**: CMake can leverage parallel compilation more effectively
5. **Better IDE Support**: CMake projects are better supported by modern IDEs
6. **Easier Maintenance**: Cleaner separation of build logic from Python packaging
7. **Future-Proof**: scikit-build-core is actively maintained and follows modern Python packaging standards

## What Changed

### Files Modified
- `pyproject.toml`: Updated to use `scikit-build-core` as the build backend
- `setup.py`: Simplified to remove custom build logic, keeping only metadata
- `CMakeLists.txt`: New file containing all build logic previously in `cocotb_build_libs.py`

### Files That Can Be Removed (After Migration)
- `cocotb_build_libs.py`: Build logic moved to CMake

### Key Features Preserved

All complex build features from the original system have been preserved:

#### Windows-Specific Features
- **Side-by-Side Assembly Manifests**: Automatically generated for proper DLL loading
- **Resource Files (.rc)**: Created for embedding manifests into libraries
- **Import Libraries**: Generated from .def files for both MSVC and MinGW
- **Application Configuration**: Created for simulator extensions
- **Compiler Detection**: Automatic handling of MSVC vs GCC/MinGW differences

#### Cross-Platform Features
- **RPATH Settings**: Proper runtime library paths for Linux and macOS
- **Library Naming**: Correct naming conventions for each platform
- **Extension Handling**: Special handling for Icarus Verilog (.vpl extension)
- **Python Integration**: Proper Python library detection and linking

#### Simulator Support
All simulator libraries are built with the same configurations:
- **VPI Libraries**: Icarus, Modelsim, VCS, IUS/Xcelium, Verilator, GHDL, Aldec, DSim
- **VHPI Libraries**: Modelsim, IUS/Xcelium, NVC, Aldec
- **FLI Libraries**: Modelsim
- **Platform-specific builds**: Some simulators only built on specific platforms

## Build Configuration

### CMake Configuration
The CMake build system automatically:
- Detects the target platform and compiler
- Configures appropriate compiler flags and warnings
- Sets up library dependencies in the correct order
- Handles Windows manifest generation
- Creates proper install targets for scikit-build-core

### Compiler Flags
The same compiler flags from the original system are preserved:
- **GCC/Clang**: Standard warnings, C++11, visibility settings, LTO where appropriate
- **MSVC**: `/permissive-`, `/W4`, disabled automatic manifests
- **Platform-specific**: Linux static libstdc++, macOS install names, Windows export symbols

### Library Dependencies
Libraries are built in dependency order:
1. `libgpilog` - Base logging functionality
2. `libpygpilog` - Python logging bridge
3. `libcocotbutils` - Utility functions
4. `libembed` - Python embedding support
5. `libgpi` - Generic Programming Interface
6. `libcocotb` - Main cocotb library
7. `simulator` - Python extension module
8. Simulator-specific libraries (VPI/VHPI/FLI)

## Building

### Requirements
The build now requires:
- CMake 3.15 or later
- scikit-build-core
- pybind11 (for Python integration)
- find_libpython (for Python library detection)

### Build Commands
Standard Python build commands work as before:
```bash
pip install .
pip install -e .  # editable install
python -m build    # build wheel
```

### Development Builds
For development, you can also use CMake directly:
```bash
mkdir build && cd build
cmake ..
make -j$(nproc)
```

## Compatibility

### API Compatibility
The migration maintains 100% API compatibility. No changes are required in:
- User code
- Test suites
- Simulation workflows
- Installation procedures

### Build Output
The generated libraries are identical to the original build system:
- Same file names and extensions
- Same library dependencies
- Same manifest files (Windows)
- Same install locations

### Platform Support
All original platform support is maintained:
- Linux (x86_64, i686)
- Windows (x86_64, i686) with MSVC and MinGW
- macOS (x86_64)

## Advanced Configuration

### CMake Variables
Advanced users can configure the build using CMake variables:
```bash
cmake -DCMAKE_BUILD_TYPE=Debug ..
cmake -DCMAKE_VERBOSE_MAKEFILE=ON ..
```

### scikit-build-core Configuration
The build can be customized via `pyproject.toml`:
```toml
[tool.scikit-build]
cmake.args = ["-DCMAKE_BUILD_TYPE=Release"]
cmake.verbose = true
```

## Troubleshooting

### Common Issues
1. **CMake not found**: Install CMake 3.15+
2. **Windows build failures**: Ensure proper Visual Studio or MinGW installation
3. **Missing dependencies**: Install required build dependencies from `pyproject.toml`

### Debug Build
For debugging build issues:
```bash
pip install -v .  # verbose output
```

### Windows-Specific
On Windows, ensure you have:
- Visual Studio with C++ tools, or
- MinGW-w64 with dlltool
- Windows SDK (for manifest generation)

## Migration Notes

### For Contributors
- Build logic is now in `CMakeLists.txt` instead of `cocotb_build_libs.py`
- Windows-specific code is handled by CMake functions
- Library dependencies are declared explicitly in CMake

### For Packagers
- The wheel building process is now handled by scikit-build-core
- All platform-specific logic is contained in CMake
- Cross-compilation support is improved through CMake toolchain files

## Future Enhancements

With this CMake foundation, future enhancements become easier:
- Better cross-compilation support
- Integration with package managers (vcpkg, Conan)
- Advanced optimization options
- Better caching and incremental builds
- Integration with modern C++ package management