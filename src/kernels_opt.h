#pragma once
#include <stdint.h>
void pointwise_prepared(const int8_t*,const int8_t*,const int32_t*,const uint64_t*,int8_t*,int,int,int);
void depthwise_prepared(const int8_t*,const int8_t*,const int32_t*,const uint64_t*,int8_t*,int);
void residual(const int8_t*,const int8_t*,int8_t*,int,const int*);
