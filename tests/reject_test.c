#include "custom_isa.h"
#include "platform.h"
volatile uint64_t trap_count,trap_cause,trap_value;
extern void test_trap_entry(void);
int main(void){
 __asm__ volatile("csrw mtvec,%0"::"r"(test_trap_entry):"memory");
 (void)xqmac8(3,1,2);
 int fail=trap_count!=1||trap_cause!=2||(trap_value&UINT64_C(0xfe00707f))!=UINT64_C(0xb);
 (void)xrequant8(123,requant_descriptor(1073741824,-8,0,-128,127));
 fail|=trap_count!=2||trap_cause!=2||(trap_value&UINT64_C(0xfe00707f))!=UINT64_C(0x100b);
 text(fail?"FAIL\n":"Stock Spike rejected both custom instructions\nPASS\n");finish(fail);return fail;
}
