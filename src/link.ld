OUTPUT_ARCH(riscv)
ENTRY(_start)
SECTIONS {
 . = 0x80000000;
 .text : { *(.text.init) *(.text .text.*) }
 .rodata : { *(.rodata .rodata.*) }
 . = ALIGN(64);
 .tohost : { *(.tohost) }
 .data : { *(.data .data.*) }
 .sdata : { __global_pointer$ = . + 0x800; *(.sdata .sdata.*) }
 . = ALIGN(8); _bss_start = .;
 .bss : { *(.bss .bss.* .sbss .sbss.*) *(COMMON) . = ALIGN(8); }
 _bss_end = .;
 . = ALIGN(16); . += 65536; _stack_top = .;
}
