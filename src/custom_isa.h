#pragma once
#include <stdint.h>
// custom-0, funct7=0, funct3=0; rd is an input/output accumulator.
static inline uint64_t xqmac8(uint64_t acc,uint64_t a,uint64_t b){
 __asm__ volatile(".insn r 0x0b, 0, 0, %0, %1, %2" : "+r"(acc) : "r"(a),"r"(b));
 return acc;
}
static inline int64_t xrequant8(uint64_t acc,uint64_t descriptor){
 uint64_t result;
 __asm__ volatile(".insn r 0x0b, 1, 0, %0, %1, %2" : "=r"(result) : "r"(acc),"r"(descriptor));
 return (int64_t)result;
}
static inline uint64_t requant_descriptor(uint32_t q,int shift,int zero,int low,int high){
 return (uint64_t)q | ((uint64_t)((unsigned)shift&63)<<32) |
        ((uint64_t)(uint8_t)zero<<38) | ((uint64_t)(uint8_t)low<<46) |
        ((uint64_t)(uint8_t)high<<54);
}
