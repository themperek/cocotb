# --- Configuration ---
BUILD_DIR := sim_build
SV_SOURCE := ../simple_dff/dff.sv
TOP_MODULE := dff
OUTPUT_VVP := $(BUILD_DIR)/dff.vvp

# C++ Lib details (inferred from cmake output in script)
LIB_NAME   := libcocotb_cpp_example.so
SHARED_LIB := $(BUILD_DIR)/$(LIB_NAME)

# Get Cocotb configuration flags
COCOTB_LIB_DIR := $(shell cocotb-config --lib-dir)
COCOTB_VPI_LIB := $(shell cocotb-config --lib-name vpi icarus)

PWD := $(shell pwd)

.PHONY: all clean run compile build_cpp

all: run

clean:
	rm -rf $(BUILD_DIR)

$(SHARED_LIB):
	mkdir -p $(BUILD_DIR)
	cd $(BUILD_DIR) && cmake .. && $(MAKE)

build_cpp: $(SHARED_LIB)

$(OUTPUT_VVP): $(SV_SOURCE) | $(SHARED_LIB)
	iverilog -s $(TOP_MODULE) -g2012 $(SV_SOURCE) -o $(OUTPUT_VVP)

compile: $(OUTPUT_VVP)

run: $(OUTPUT_VVP) $(SHARED_LIB)
	export GPI_USERS=$(PWD)/$(SHARED_LIB),cocotb_entry_point; \
	cd $(BUILD_DIR) && \
	vvp -M $(COCOTB_LIB_DIR) -m $(COCOTB_VPI_LIB) $(notdir $(OUTPUT_VVP))