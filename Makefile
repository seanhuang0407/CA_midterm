SHELL := /bin/bash
CROSS ?= riscv-none-elf-
CC_HOST ?= gcc
COMMON = -std=c11 -O2 -Wall -Wextra -Werror -fno-tree-vectorize -fno-tree-slp-vectorize -fno-builtin -Isrc -Ibuild
RVFLAGS = $(COMMON) -march=rv64imc_zicsr -mabi=lp64 -mcmodel=medany -msmall-data-limit=0 -ffreestanding -fno-stack-protector
RVLINK = -nostdlib -nostartfiles -Wl,-T,src/link.ld
BOOT = src/start.S src/platform.c
SOURCES = src/main.c src/kernels.c src/platform.c
OPT_SOURCES = src/main.c src/kernels_opt.c src/platform.c
OPT_HEADERS = src/kernels_opt.h src/quant_math.h src/custom_isa.h
PREPARED = S P X1 XR X2
S_FLAGS = -DPACKED=0 -DUSE_QMAC=0 -DUSE_REQUANT=0
P_FLAGS = -DPACKED=1 -DUSE_QMAC=0 -DUSE_REQUANT=0
X1_FLAGS = -DPACKED=1 -DUSE_QMAC=1 -DUSE_REQUANT=0
XR_FLAGS = -DPACKED=1 -DUSE_QMAC=0 -DUSE_REQUANT=1
X2_FLAGS = -DPACKED=1 -DUSE_QMAC=1 -DUSE_REQUANT=1
WORKLOADS = B0 B1 $(PREPARED) micro $(addprefix micro-,$(PREPARED))
TEST_ELFS = isa-test reject-test kernel-test rv32-reject

define artifacts
	$(CROSS)objdump -d -M no-aliases,numeric $@ > $(@:.elf=.dis)
	$(CROSS)nm -n -S $@ > $(@:.elf=.symbols)
	$(CROSS)size $@ > $(@:.elf=.size)
endef

.PHONY: all export host-test test custom-spike isa-test benchmark clean
all: $(addprefix build/,$(addsuffix .elf,$(WORKLOADS)))
build:
	mkdir -p $@
export:
	python3 scripts/export_model.py
build/model_data.h: | build
	python3 scripts/export_model.py
build/host-B%: $(SOURCES) src/kernels.h src/platform.h build/model_data.h
	$(CC_HOST) $(COMMON) -DHOST -DOPT=$* $(SOURCES) -o $@
host-test: build/host-B0 build/host-B1
	./build/host-B0
	./build/host-B1
build/libkernels.so: src/kernels.c src/kernels.h
	$(CC_HOST) $(COMMON) -fPIC -shared src/kernels.c -o $@
build/libquant-opt.so: tests/quant_export.c src/quant_math.h
	$(CC_HOST) $(COMMON) -fPIC -shared tests/quant_export.c -o $@
test: host-test build/libkernels.so build/libquant-opt.so
	python3 tests/test_quant.py

build/B%.elf: $(SOURCES) src/start.S src/link.ld src/kernels.h src/platform.h build/model_data.h
	$(CROSS)gcc $(RVFLAGS) -DOPT=$* $(RVLINK) -Wl,-Map,$(@:.elf=.map) src/start.S $(SOURCES) -lgcc -o $@
	$(artifacts)
$(addprefix build/,$(addsuffix .elf,$(PREPARED))): build/%.elf: $(OPT_SOURCES) $(OPT_HEADERS) src/start.S src/link.ld build/model_data.h
	$(CROSS)gcc $(RVFLAGS) -DPREPARED $($*_FLAGS) $(RVLINK) -Wl,-Map,$(@:.elf=.map) src/start.S $(OPT_SOURCES) -lgcc -o $@
	$(artifacts)
build/micro.elf: src/micro.c src/kernels.c $(BOOT) src/link.ld src/kernels.h src/platform.h
	$(CROSS)gcc $(RVFLAGS) -DOPT=0 $(RVLINK) src/start.S src/micro.c src/kernels.c src/platform.c -lgcc -o $@
	$(artifacts)
$(addprefix build/micro-,$(addsuffix .elf,$(PREPARED))): build/micro-%.elf: src/micro_prepared.c src/kernels_opt.c $(OPT_HEADERS) $(BOOT) src/link.ld
	$(CROSS)gcc $(RVFLAGS) $($*_FLAGS) $(RVLINK) src/start.S src/micro_prepared.c src/kernels_opt.c src/platform.c -lgcc -o $@
	$(artifacts)

custom-spike:
	bash scripts/build_spike_custom.sh
build/isa_vectors.h: tests/gen_isa_vectors.py | build
	python3 tests/gen_isa_vectors.py
build/isa-test.elf: tests/isa_test.c tests/isa_alias.S tests/trap.S $(BOOT) src/link.ld src/custom_isa.h build/isa_vectors.h
	$(CROSS)gcc $(RVFLAGS) $(RVLINK) $(BOOT) tests/isa_test.c tests/isa_alias.S tests/trap.S -lgcc -o $@
build/reject-test.elf: tests/reject_test.c tests/trap.S $(BOOT) src/link.ld src/custom_isa.h
	$(CROSS)gcc $(RVFLAGS) $(RVLINK) $(BOOT) tests/reject_test.c tests/trap.S -lgcc -o $@
build/kernel-test.elf: tests/kernel_test.c src/kernels_opt.c $(OPT_HEADERS) $(BOOT) src/link.ld
	$(CROSS)gcc $(RVFLAGS) $(X2_FLAGS) $(RVLINK) $(BOOT) tests/kernel_test.c src/kernels_opt.c -lgcc -o $@
build/rv32-reject.elf: tests/rv32_reject.S src/link.ld
	$(CROSS)gcc -march=rv32imc_zicsr -mabi=ilp32 $(RVLINK) tests/rv32_reject.S -o $@
isa-test: custom-spike $(addprefix build/,$(addsuffix .elf,$(TEST_ELFS)))
	bash scripts/test_isa.sh
benchmark: all custom-spike
	bash scripts/benchmark.sh

$(addprefix build/,$(addsuffix .elf,$(WORKLOADS) $(TEST_ELFS))) build/libkernels.so build/libquant-opt.so build/host-B0 build/host-B1: Makefile | build
clean:
	python3 -c "import shutil; shutil.rmtree('build',ignore_errors=True)"
