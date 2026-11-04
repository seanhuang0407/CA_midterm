.section .text.init
.option norvc
.global _start
_start:
la sp,_stack_top
la t1,handler
csrw mtvec,t1
li t0,0
.insn r 0x0b,0,0,a0,a1,a2
.insn r 0x0b,1,0,a0,a1,a2
li t1,2
bne t0,t1,fail
li t1,1
j exit
fail:
li t1,3
exit:
la t2,tohost
sw t1,0(t2)
1: wfi
j 1b
.balign 4
handler:
csrr t1,mcause
li t2,2
bne t1,t2,fail
addi t0,t0,1
csrr t1,mepc
addi t1,t1,4
csrw mepc,t1
mret
.section .tohost,"aw",@progbits
.balign 64
.global tohost
tohost: .dword 0
.balign 64
.global fromhost
fromhost: .dword 0
