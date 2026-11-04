.text
.balign 4
.global test_trap_entry
.type test_trap_entry,@function
test_trap_entry:
addi sp,sp,-16
sd t0,0(sp)
sd t1,8(sp)
la t0,trap_count
ld t1,0(t0)
addi t1,t1,1
sd t1,0(t0)
la t0,trap_cause
csrr t1,mcause
sd t1,0(t0)
la t0,trap_value
csrr t1,mtval
sd t1,0(t0)
csrr t0,mepc
addi t0,t0,4
csrw mepc,t0
ld t0,0(sp)
ld t1,8(sp)
addi sp,sp,16
mret
