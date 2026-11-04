SHELL := /bin/bash
CROSS ?= riscv-none-elf-
CC_HOST ?= gcc
COMMON = -std=c11 -O2 -Wall -Wextra -Werror -fno-tree-vectorize -fno-tree-slp-vectorize -fno-builtin -Isrc -Ibuild
RVFLAGS = $(COMMON) -march=rv64imc_zicsr -mabi=lp64 -mcmodel=medany -msmall-data-limit=0 -ffreestanding -fno-stack-protector
SOURCES = src/main.c src/kernels.c src/platform.c
.PHONY: all export host-test benchmark clean
all: build/B0.elf build/B1.elf
export:
	python3 scripts/export_model.py
build/model_data.h:
	python3 scripts/export_model.py
build/host-B%: $(SOURCES) src/kernels.h src/platform.h build/model_data.h
	$(CC_HOST) $(COMMON) -DHOST -DOPT=$* $(SOURCES) -o $@
host-test: build/host-B0 build/host-B1
	./build/host-B0
	./build/host-B1
build/B%.elf: $(SOURCES) src/start.S src/link.ld src/kernels.h src/platform.h build/model_data.h
	$(CROSS)gcc $(RVFLAGS) -DOPT=$* -nostdlib -nostartfiles -Wl,-T,src/link.ld,-Map,build/B$*.map src/start.S $(SOURCES) -lgcc -o $@
	$(CROSS)objdump -d -M no-aliases,numeric $@ > build/B$*.dis
	$(CROSS)nm -n -S $@ > build/B$*.symbols
	$(CROSS)size $@ > build/B$*.size
benchmark: all
	bash scripts/benchmark.sh
clean:
	python3 -c "import shutil; shutil.rmtree('build',ignore_errors=True)"
build/micro.elf: src/micro.c src/kernels.c src/platform.c src/start.S src/link.ld src/kernels.h src/platform.h
	$(CROSS)gcc $(RVFLAGS) -DOPT=0 -nostdlib -nostartfiles -Wl,-T,src/link.ld src/start.S src/micro.c src/kernels.c src/platform.c -lgcc -o $@
	$(CROSS)objdump -d -M no-aliases,numeric $@ > build/micro.dis
	$(CROSS)nm -n -S $@ > build/micro.symbols
	$(CROSS)size $@ > build/micro.size
all: build/micro.elf
.PHONY: test
test: host-test build/libkernels.so
	python3 tests/test_quant.py
build/libkernels.so: src/kernels.c src/kernels.h
	$(CC_HOST) $(COMMON) -fPIC -shared src/kernels.c -o $@
