#pragma once
#include <stdint.h>
void text(const char*);
void number(uint64_t);
void finish(int);
static inline uint64_t retired(void){
#ifdef HOST
return 0;
#else
uint64_t n;__asm__ volatile("csrr %0, minstret":"=r"(n)::"memory");return n;
#endif
}
