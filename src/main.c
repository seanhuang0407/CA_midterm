#ifdef PREPARED
#include "kernels_opt.h"
#else
#include "kernels.h"
#endif
#include "platform.h"
#include "model_data.h"
static int8_t a[56*56*72] __attribute__((aligned(8)));
static int8_t b[56*56*72] __attribute__((aligned(8)));
static int8_t c[56*56*24] __attribute__((aligned(8)));
static int8_t d[56*56*24] __attribute__((aligned(8)));
static int8_t fc_out[P_fc_n] __attribute__((aligned(8)));
static volatile uint64_t samples[6];
static const int ap[]={P_add_a_zero,P_add_b_zero,P_add_out_zero,P_add_aq,P_add_as,P_add_bq,P_add_bs,P_add_oq,P_add_os};
static int check(const char*name,const int8_t*x,const int8_t*y,int len){
 uint64_t errors=0,hash=2166136261u;for(int i=0;i<len;i++){errors+=x[i]!=y[i];hash=(uint32_t)((hash^(uint8_t)x[i])*16777619u);}
 text(name);text(" mismatches=");number(errors);text(" checksum=");number(hash);text("\n");return errors!=0;
}
int main(void){
 samples[0]=retired();
#ifdef PREPARED
 pointwise_prepared(block_input,expand_w,expand_folded_b,expand_desc,a,3136,24,72);
#else
 pointwise(block_input,expand_w,expand_b,expand_mult,expand_shift,a,3136,24,72,P_expand_input_zero,P_expand_output_zero,P_expand_min);
#endif
 samples[1]=retired();
#ifdef PREPARED
 depthwise_prepared(a,depthwise_w,depthwise_b,depthwise_desc,b,P_depthwise_input_zero);
#else
 depthwise(a,depthwise_w,depthwise_b,depthwise_mult,depthwise_shift,b,P_depthwise_input_zero,P_depthwise_output_zero,P_depthwise_min);
#endif
 samples[2]=retired();
#ifdef PREPARED
 pointwise_prepared(b,project_w,project_folded_b,project_desc,c,3136,72,24);
#else
 pointwise(b,project_w,project_b,project_mult,project_shift,c,3136,72,24,P_project_input_zero,P_project_output_zero,P_project_min);
#endif
 samples[3]=retired();
 residual(c,block_input,d,3136*24,ap);
 samples[4]=retired();
#ifdef PREPARED
 pointwise_prepared(fc_input,fc_w,fc_folded_b,fc_desc,fc_out,1,P_fc_k,P_fc_n);
#else
 pointwise(fc_input,fc_w,fc_b,fc_mult,fc_shift,fc_out,1,P_fc_k,P_fc_n,P_fc_input_zero,P_fc_output_zero,P_fc_min);
#endif
 samples[5]=retired();
 const char*names[]={"expand","depthwise","project","residual","fc"};
 for(int i=0;i<5;i++){text("ROI ");text(names[i]);text(" instret=");number(samples[i+1]-samples[i]);text("\n");}
 int err=0;err|=check("expand",a,ref_expand,sizeof a);err|=check("depthwise",b,ref_depthwise,sizeof b);err|=check("project",c,ref_project,sizeof c);err|=check("residual",d,ref_residual,sizeof d);err|=check("fc",fc_out,ref_fc,sizeof fc_out);
 text(err?"FAIL\n":"PASS\n");finish(err);return err;
}
