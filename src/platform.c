#include "platform.h"
#ifdef HOST
#include <stdio.h>
#include <stdlib.h>
void text(const char*s){fputs(s,stdout);}
void finish(int code){exit(code);}
#else
volatile uint64_t tohost __attribute__((section(".tohost"),aligned(64)));
volatile uint64_t fromhost __attribute__((section(".tohost"),aligned(64)));
static void write_host(const char*s,uint64_t n){
 volatile uint64_t msg[8] __attribute__((aligned(64)))={64,1,(uint64_t)s,n,0,0,0,0};
 __asm__ volatile("fence rw,rw":::"memory");tohost=(uint64_t)msg;
 while(!fromhost){}fromhost=0;__asm__ volatile("fence rw,rw":::"memory");
}
void text(const char*s){uint64_t n=0;while(s[n])n++;write_host(s,n);}
void finish(int code){tohost=((uint64_t)code<<1)|1;for(;;)__asm__ volatile("wfi");}
#endif
void number(uint64_t x){char b[24];int n=0;do{b[n++]='0'+x%10;x/=10;}while(x);char out[24];for(int i=0;i<n;i++)out[i]=b[n-i-1];out[n]=0;text(out);}
