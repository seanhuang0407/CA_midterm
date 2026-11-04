#include "custom_isa.h"
#include "platform.h"
#include "isa_vectors.h"
volatile uint64_t trap_count,trap_cause,trap_value;
extern void test_trap_entry(void);
extern uint64_t mac_alias_a(uint64_t,uint64_t),mac_alias_b(uint64_t,uint64_t),mac_alias_all(uint64_t),mac_equal_inputs(uint64_t,uint64_t),mac_zero_a(uint64_t,uint64_t),mac_zero_b(uint64_t,uint64_t),mac_discard(uint64_t,uint64_t);
extern uint64_t req_alias_a(uint64_t,uint64_t),req_alias_b(uint64_t,uint64_t),req_alias_all(uint64_t),req_zero_a(uint64_t),req_zero_b(uint64_t),req_discard(uint64_t,uint64_t),invalid_encoding(uint64_t,uint64_t);
static uint64_t checks;
static void eq(const char*name,uint64_t got,uint64_t want,uint64_t index){
 checks++;
 if(got!=want){text("FAIL ");text(name);text(" index=");number(index);text(" got=");number(got);text(" expected=");number(want);text("\n");finish(1);}
}
int main(void){
 __asm__ volatile("csrw mtvec,%0"::"r"(test_trap_entry):"memory");
 for(unsigned i=0;i<sizeof mac_cases/sizeof mac_cases[0];i++){
  const struct mac_case*t=&mac_cases[i];
  eq("mac",xqmac8(t->old,t->a,t->b),t->out,i);
  eq("mac rd=rs1",mac_alias_a(t->a,t->b),t->alias_a,i);
  eq("mac rd=rs2",mac_alias_b(t->a,t->b),t->alias_b,i);
  eq("mac all alias",mac_alias_all(t->a),t->alias_all,i);
  eq("mac rs1=rs2",mac_equal_inputs(t->old,t->a),t->equal_inputs,i);
  eq("mac rs1=x0",mac_zero_a(t->old,t->a),t->zero_sources,i);
  eq("mac rs2=x0",mac_zero_b(t->old,t->a),t->zero_sources,i);
  eq("mac rd=x0",mac_discard(t->a,t->b),t->a,i);
 }
 for(unsigned i=0;i<sizeof req_cases/sizeof req_cases[0];i++){
  const struct req_case*t=&req_cases[i];
  eq("req",(uint64_t)xrequant8(t->a,t->d),t->out,i);
  eq("req rd=rs1",req_alias_a(t->a,t->d),t->out,i);
  eq("req rd=rs2",req_alias_b(t->a,t->d),t->out,i);
  eq("req all alias",req_alias_all(t->d),t->alias_all,i);
  eq("req rs1=x0",req_zero_a(t->d),t->zero_input,i);
  eq("req rs2=x0",req_zero_b(t->a),0,i);
  eq("req rd=x0",req_discard(t->a,t->d),t->a,i);
 }
 eq("no unexpected traps",trap_count,0,0);
 const uint64_t good=requant_descriptor(1073741824,-8,0,-128,127);
 const uint64_t bad[]={good|(UINT64_C(1)<<62),good|(UINT64_C(1)<<63),good|UINT64_C(0x80000000),requant_descriptor(1,1,0,-128,127),requant_descriptor(1,-32,0,-128,127),requant_descriptor(1,0,0,10,-10)};
 for(unsigned i=0;i<sizeof bad/sizeof bad[0];i++){
  uint64_t before=trap_count;
  eq("illegal preserves rd",req_alias_a(123,bad[i]),123,i);eq("illegal count",trap_count,before+1,i);eq("illegal cause",trap_cause,2,i);eq("illegal encoding",trap_value&UINT64_C(0xfe00707f),UINT64_C(0x100b),i);
  (void)req_discard(123,bad[i]);eq("illegal even rd=x0",trap_count,before+2,i);eq("illegal cause rd=x0",trap_cause,2,i);
 }
 uint64_t before=trap_count;eq("reserved encoding preserves rd",invalid_encoding(1,2),1,0);eq("reserved encoding trap",trap_count,before+1,0);eq("reserved encoding cause",trap_cause,2,0);
 text("Xqmac8 vectors=");number(sizeof mac_cases/sizeof mac_cases[0]);text(" Xrequant8 vectors=");number(sizeof req_cases/sizeof req_cases[0]);text("\nassertions=");number(checks);text(" expected_illegal_traps=");number(trap_count);text("\nPASS\n");finish(0);return 0;
}
