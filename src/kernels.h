#pragma once
#include <stdint.h>
int32_t qmul(int32_t x,int32_t q,int s);
int8_t requant(int32_t x,int32_t q,int s,int zero,int low);
void pointwise(const int8_t*x,const int8_t*w,const int32_t*b,const int32_t*q,const int32_t*s,int8_t*y,int rows,int k,int n,int iz,int oz,int lo);
void depthwise(const int8_t*x,const int8_t*w,const int32_t*b,const int32_t*q,const int32_t*s,int8_t*y,int iz,int oz,int lo);
void residual(const int8_t*a,const int8_t*b,int8_t*y,int len,const int*p);
