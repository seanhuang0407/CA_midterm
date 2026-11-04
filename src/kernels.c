#include "kernels.h"
#ifndef OPT
#define OPT 0
#endif
#define NOINLINE __attribute__((noinline))
// Inputs are bounded by the exported model; left shifts must fit signed INT32.
NOINLINE int32_t qmul(int32_t x,int32_t q,int s){
 int64_t a=(int64_t)x*((int64_t)1<<(s>0?s:0));
 int64_t p=a*q;
 int32_t z=(int32_t)((p+(p>=0?((int64_t)1<<30):1-((int64_t)1<<30)))/((int64_t)1<<31));
 int r=s<0?-s:0;
 if(r){uint32_t mask=((uint32_t)1<<r)-1;z=(z>>r)+((z&(int32_t)mask)>((int32_t)(mask>>1)+(z<0)));}
 return z;
}
NOINLINE int8_t requant(int32_t x,int32_t q,int s,int zero,int low){
 int32_t v=qmul(x,q,s)+zero;return (int8_t)(v<low?low:v>127?127:v);
}
NOINLINE void pointwise(const int8_t*x,const int8_t*w,const int32_t*b,const int32_t*q,const int32_t*s,int8_t*y,int rows,int k,int n,int iz,int oz,int lo){
 for(int row=0;row<rows;row++)for(int c=0;c<n;c++){
  int32_t acc=b[c];const int8_t*a=x+row*k,*v=w+c*k;int i=0;
#if OPT
  // Four independent accumulators shorten the scalar dependency chain.
  int32_t a0=0,a1=0,a2=0,a3=0;
  for(;i+3<k;i+=4){a0+=((int)a[i]-iz)*v[i];a1+=((int)a[i+1]-iz)*v[i+1];a2+=((int)a[i+2]-iz)*v[i+2];a3+=((int)a[i+3]-iz)*v[i+3];}
  acc+=a0+a1+a2+a3;
#endif
  for(;i<k;i++)acc+=((int)a[i]-iz)*v[i];
  y[row*n+c]=requant(acc,q[c],s[c],oz,lo);
 }
}
NOINLINE void depthwise(const int8_t*x,const int8_t*w,const int32_t*b,const int32_t*q,const int32_t*s,int8_t*y,int iz,int oz,int lo){
 for(int h=0;h<56;h++)for(int col=0;col<56;col++)for(int c=0;c<72;c++){
  int32_t acc=b[c];
  for(int kh=0;kh<3;kh++)for(int kw=0;kw<3;kw++){
   int ih=h+kh-1,iw=col+kw-1;
   int a=(ih>=0&&ih<56&&iw>=0&&iw<56)?x[(ih*56+iw)*72+c]:iz;
   acc+=(a-iz)*w[(kh*3+kw)*72+c];
  }
  y[(h*56+col)*72+c]=requant(acc,q[c],s[c],oz,lo);
 }
}
NOINLINE void residual(const int8_t*a,const int8_t*b,int8_t*y,int len,const int*p){
 for(int i=0;i<len;i++){
  int32_t av=qmul(((int)a[i]-p[0])*(1<<20),p[3],p[4]);
  int32_t bv=qmul(((int)b[i]-p[1])*(1<<20),p[5],p[6]);
  y[i]=requant(av+bv,p[7],p[8],p[2],-128);
 }
}
