#include "kernels_opt.h"
#include "quant_math.h"
#include "custom_isa.h"
#include "platform.h"
static int8_t xbuf[3*72+16] __attribute__((aligned(8))),wbuf[3*72+16] __attribute__((aligned(8))),out[9];
static int32_t bias[3];static uint64_t desc[3];
int main(void){
 int checks=0;
 // K=0..65, aligned/unaligned rows and weights, tails, nonzero zero-points.
 for(int k=0;k<=65;k++)for(int offset=0;offset<8;offset++)for(int z=-128;z<=127;z+=85){
  int8_t*x=xbuf+offset,*w=wbuf+(7-offset);
  for(int i=0;i<3*k;i++){x[i]=(i*13+offset*7)%256-128;w[i]=(i*7+offset*11)%256-128;}
  for(int c=0;c<3;c++){
   int sum=0;for(int i=0;i<k;i++)sum+=w[c*k+i];bias[c]=123-c*17-z*sum;
   desc[c]=requant_descriptor(1073741824,-8,c-4,-128,127);
  }
  pointwise_prepared(x,w,bias,desc,out,3,k,3);
  for(int row=0;row<3;row++)for(int c=0;c<3;c++){
   int64_t acc=123-c*17;for(int i=0;i<k;i++)acc+=((int)x[row*k+i]-z)*w[c*k+i];
   int8_t expected=scalar_requant((int32_t)acc,1073741824,-8,c-4,-128,127);checks++;
   if(out[row*3+c]!=expected){text("FAIL tail/alignment k=");number(k);text(" offset=");number(offset);text("\n");finish(1);}
  }
 }
 text("Kernel tail/alignment comparisons=");number(checks);text("\nPASS\n");finish(0);return 0;
}
