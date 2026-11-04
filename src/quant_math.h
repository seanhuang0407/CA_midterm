#pragma once
#include <stdint.h>
// TFLite double-rounding reference. Callers must bound any positive left shift.
static inline int32_t scalar_qmul(int32_t x,int32_t q,int s){
 int64_t a=(int64_t)x*((int64_t)1<<(s>0?s:0));
 int64_t p=a*q;
 int32_t z=(int32_t)((p+(p>=0?((int64_t)1<<30):1-((int64_t)1<<30)))/((int64_t)1<<31));
 int r=s<0?-s:0;
 if(r){uint32_t mask=((uint32_t)1<<r)-1;z=(z>>r)+((z&(int32_t)mask)>((int32_t)(mask>>1)+(z<0)));}
 return z;
}
static inline int8_t scalar_requant(int32_t x,int32_t q,int s,int zero,int low,int high){
 int64_t v=(int64_t)scalar_qmul(x,q,s)+zero;
 return (int8_t)(v<low?low:v>high?high:v);
}
static inline int descriptor_byte(uint64_t d,int bit){
 unsigned v=(unsigned)(d>>bit)&255;return v<128?(int)v:(int)v-256;
}
static inline int8_t scalar_descriptor(int32_t x,uint64_t d){
 // Exported descriptors guarantee a nonnegative Q31 coefficient and s<=0.
 // Express these bounds so the software control needs no left-shift path.
 int s=-(int)((64-((unsigned)(d>>32)&63))&31);
 return scalar_requant(x,(int32_t)(d&UINT64_C(0x7fffffff)),s,descriptor_byte(d,38),descriptor_byte(d,46),descriptor_byte(d,54));
}
