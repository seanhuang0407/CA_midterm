#include "kernels.h"
#include "platform.h"
static int8_t x[128],w[128],y;
int main(void){
 int32_t b=123,q=1073741824,s=-8;
 for(int i=0;i<128;i++){x[i]=(i*13%255)-128;w[i]=(i*7%255)-128;}
 // Independently computed Python integer reference: accumulator=15959, output=27.
 int8_t expected=27;
 uint64_t a=retired();pointwise(x,w,&b,&q,&s,&y,1,128,1,3,-4,-128);uint64_t z=retired();
 text("ROI micro instret=");number(z-a);text("\n");
 int fail=y!=expected;text(fail?"FAIL\n":"PASS\n");finish(fail);return fail;
}
