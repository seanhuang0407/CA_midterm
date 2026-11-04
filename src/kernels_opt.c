#include "kernels_opt.h"
#include "quant_math.h"
#include "custom_isa.h"
#ifndef PACKED
#define PACKED 0
#endif
#ifndef USE_QMAC
#define USE_QMAC 0
#endif
#ifndef USE_REQUANT
#define USE_REQUANT 0
#endif
#define NOINLINE __attribute__((noinline))
static inline int8_t output_quant(int32_t x,uint64_t d){
#if USE_REQUANT
 return (int8_t)xrequant8((uint64_t)(int64_t)x,d);
#else
 return scalar_descriptor(x,d);
#endif
}
#if PACKED
static inline uint64_t load8(const int8_t*p){
 uint64_t v;
 if(((uintptr_t)p&7)==0){
  // memcpy avoids aliasing violations; alignment allows a single RV64 ld.
  __builtin_memcpy(&v,__builtin_assume_aligned(p,8),8);
 }else{
  v=0;for(int i=0;i<8;i++)v|=(uint64_t)(uint8_t)p[i]<<(8*i);
 }
 return v;
}
#if !USE_QMAC
static inline int lane(uint64_t x,int i){return (int)((((x>>(8*i))&255)^128))-128;}
#endif
#endif
NOINLINE void pointwise_prepared(const int8_t*x,const int8_t*w,const int32_t*b,const uint64_t*d,int8_t*y,int rows,int k,int n){
 for(int row=0;row<rows;row++)for(int c=0;c<n;c++){
  const int8_t*a=x+row*k,*v=w+c*k;uint32_t acc=(uint32_t)b[c];int i=0;
#if PACKED
  for(;i+7<k;i+=8){
   uint64_t aa=load8(a+i),ww=load8(v+i);
#if USE_QMAC
   acc=(uint32_t)xqmac8(acc,aa,ww);
#else
   // Same packed ld layout as X1, but eight scalar signed multiplications.
   acc+=(uint32_t)(lane(aa,0)*lane(ww,0));
   acc+=(uint32_t)(lane(aa,1)*lane(ww,1));
   acc+=(uint32_t)(lane(aa,2)*lane(ww,2));
   acc+=(uint32_t)(lane(aa,3)*lane(ww,3));
   acc+=(uint32_t)(lane(aa,4)*lane(ww,4));
   acc+=(uint32_t)(lane(aa,5)*lane(ww,5));
   acc+=(uint32_t)(lane(aa,6)*lane(ww,6));
   acc+=(uint32_t)(lane(aa,7)*lane(ww,7));
#endif
  }
#else
  uint32_t a0=0,a1=0,a2=0,a3=0;
  for(;i+3<k;i+=4){a0+=(uint32_t)(a[i]*v[i]);a1+=(uint32_t)(a[i+1]*v[i+1]);a2+=(uint32_t)(a[i+2]*v[i+2]);a3+=(uint32_t)(a[i+3]*v[i+3]);}
  acc+=a0+a1+a2+a3;
#endif
  for(;i<k;i++)acc+=(uint32_t)(a[i]*v[i]);
  y[row*n+c]=output_quant((int32_t)acc,d[c]);
 }
}
NOINLINE void depthwise_prepared(const int8_t*x,const int8_t*w,const int32_t*b,const uint64_t*d,int8_t*y,int iz){
 for(int h=0;h<56;h++)for(int col=0;col<56;col++)for(int c=0;c<72;c++){
  int32_t acc=b[c];
  for(int kh=0;kh<3;kh++)for(int kw=0;kw<3;kw++){
   int ih=h+kh-1,iw=col+kw-1;
   int a=(ih>=0&&ih<56&&iw>=0&&iw<56)?x[(ih*56+iw)*72+c]:iz;
   acc+=(a-iz)*w[(kh*3+kw)*72+c];
  }
  y[(h*56+col)*72+c]=output_quant(acc,d[c]);
 }
}
NOINLINE void residual(const int8_t*a,const int8_t*b,int8_t*y,int len,const int*p){
 for(int i=0;i<len;i++){
  int32_t av=scalar_qmul(((int)a[i]-p[0])*(1<<20),p[3],p[4]);
  int32_t bv=scalar_qmul(((int)b[i]-p[1])*(1<<20),p[5],p[6]);
  // Keep ADD identical in every prepared configuration (no early INT8 clamp).
  y[i]=scalar_requant(av+bv,p[7],p[8],p[2],-128,127);
 }
}
