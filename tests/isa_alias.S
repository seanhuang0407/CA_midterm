.text
.option push
.option norvc
.macro function name
.global \name
.type \name,@function
\name:
.endm
function mac_alias_a
.insn r 0x0b,0,0,a0,a0,a1
ret
function mac_alias_b
.insn r 0x0b,0,0,a1,a0,a1
mv a0,a1
ret
function mac_alias_all
.insn r 0x0b,0,0,a0,a0,a0
ret
function mac_equal_inputs
.insn r 0x0b,0,0,a0,a1,a1
ret
function mac_zero_a
.insn r 0x0b,0,0,a0,zero,a1
ret
function mac_zero_b
.insn r 0x0b,0,0,a0,a1,zero
ret
function mac_discard
.insn r 0x0b,0,0,zero,a0,a1
ret
function req_alias_a
.insn r 0x0b,1,0,a0,a0,a1
ret
function req_alias_b
.insn r 0x0b,1,0,a1,a0,a1
mv a0,a1
ret
function req_alias_all
.insn r 0x0b,1,0,a0,a0,a0
ret
function req_zero_a
.insn r 0x0b,1,0,a0,zero,a0
ret
function req_zero_b
.insn r 0x0b,1,0,a0,a0,zero
ret
function req_discard
.insn r 0x0b,1,0,zero,a0,a1
ret
function invalid_encoding
.insn r 0x0b,0,1,a0,a0,a1
ret
.option pop
