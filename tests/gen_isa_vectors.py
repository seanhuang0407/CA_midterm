#!/usr/bin/env python3
"""Python arbitrary-precision oracle, independent of the Spike/C implementation."""
import random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MASK=(1<<64)-1
def signed(v,bits):
    v&=(1<<bits)-1
    return v-(1<<bits) if v>>(bits-1) else v

def mac(acc,a,b):
    dot=sum(signed(a>>(8*i),8)*signed(b>>(8*i),8) for i in range(8))
    return signed(signed(acc,32)+dot,32)&MASK

def descriptor(q,s,z,lo,hi):
    return q|((s&63)<<32)|((z&255)<<38)|((lo&255)<<46)|((hi&255)<<54)

def requant(a,d):
    q=d&0xffffffff;s=signed(d>>32,6);z=signed(d>>38,8);lo=signed(d>>46,8);hi=signed(d>>54,8)
    # High multiply rounds halfway toward +infinity, followed by a separate
    # power-of-two rounding halfway away from zero. No fixed-width intermediates.
    high=(signed(a,32)*q+(1<<30))//(1<<31)
    if s<0:
        high=(1 if high>=0 else -1)*((abs(high)+(1<<(-s-1)))//(1<<-s))
    return min(hi,max(lo,high+z))&MASK

def main():
    rng=random.Random(0xCA2026)
    patterns=[0,MASK,0x8080808080808080,0x7f7f7f7f7f7f7f7f,0x807f01ff00fe0280,0x0102030405060708]
    mc=[(a,b,old&MASK) for a in patterns for b in patterns for old in [0,1,-1,0x7fffffff,0x80000000,0xdeadbeef12345678]]
    mc += [(rng.getrandbits(64),rng.getrandbits(64),rng.getrandbits(64)) for _ in range(10000)]
    rc=[]
    for a in [-2147483648,-1001,-3,-1,0,1,3,1001,2147483647]:
        for q in [0,1,1<<30,(1<<31)-1]:
            for s in [-31,-19,-1,0]:
                for z,lo,hi in [(-128,-128,127),(127,-128,127),(0,-10,10),(1,1,1)]:
                    rc.append((a&MASK,descriptor(q,s,z,lo,hi)))
    for _ in range(10000):
        lo=rng.randint(-128,127);hi=rng.randint(lo,127)
        rc.append((rng.getrandbits(64),descriptor(rng.randrange(1<<31),rng.randint(-31,0),rng.randint(-128,127),lo,hi)))
    out=ROOT/'build/isa_vectors.h';out.parent.mkdir(exist_ok=True)
    with out.open('w') as f:
        f.write('#pragma once\n#include <stdint.h>\n')
        f.write('struct mac_case {uint64_t a,b,old,out,alias_a,alias_b,alias_all,equal_inputs,zero_sources;};\nstatic const struct mac_case mac_cases[]={\n')
        def emit(values):f.write('{'+','.join('UINT64_C(0x%016x)'%v for v in values)+'},\n')
        for a,b,old in mc:emit([a,b,old,mac(old,a,b),mac(a,a,b),mac(b,a,b),mac(a,a,a),mac(old,a,a),signed(old,32)&MASK])
        f.write('};\nstruct req_case {uint64_t a,d,out,zero_input,alias_all;};\nstatic const struct req_case req_cases[]={\n')
        for a,d in rc:emit([a,d,requant(a,d),requant(0,d),requant(d,d)])
        f.write('};\n')
    print('Xqmac8 vectors:',len(mc),'Xrequant8 vectors:',len(rc),'seed=0xCA2026')
if __name__=='__main__':main()
