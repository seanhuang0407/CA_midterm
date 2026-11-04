#include "kernels_opt.h"
#include "custom_isa.h"
#include "platform.h"
static int8_t x[128] __attribute__((aligned(8))),w[128] __attribute__((aligned(8))),y;
int main(void){
 int sum=0;for(int i=0;i<128;i++){x[i]=(i*13%255)-128;w[i]=(i*7%255)-128;sum+=w[i];}
 int32_t b=123-3*sum;uint64_t d=requant_descriptor(1073741824,-8,-4,-128,127);
 uint64_t a=retired();pointwise_prepared(x,w,&b,&d,&y,1,128,1);uint64_t z=retired();
 text("ROI micro instret=");number(z-a);text("\n");
 int fail=y!=27;text(fail?"FAIL\n":"PASS\n");finish(fail);return fail;
}
