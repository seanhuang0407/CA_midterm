#!/usr/bin/env python3
"""Independent Python integer arithmetic versus compiled C, with signed edge cases."""
import ctypes,sys,unittest,random
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from export_model import mul
from profile import category
from gen_isa_vectors import descriptor,requant as python_requant,signed
class QuantTest(unittest.TestCase):
    def test_qmul(self):
        c=ctypes.CDLL(str(ROOT/'build/libkernels.so'));f=c.qmul;f.argtypes=[ctypes.c_int32,ctypes.c_int32,ctypes.c_int];f.restype=ctypes.c_int32
        rng=np.random.default_rng(17)
        cases=[(x,q,s) for x in [-2147483648,-1001,-3,-1,0,1,3,1001,2147483647] for q in [0,1,1073741824,2147483647] for s in [-31,-19,-1,0]]
        for _ in range(10000):
            s=int(rng.integers(-31,5));limit=(1<<31)//(1<<max(s,0));x=int(rng.integers(-limit,limit));q=int(rng.integers(0,1<<31));cases.append((x,q,s))
        for x,q,s in cases:self.assertEqual(f(x,q,s),int(mul(x,q,s)),(x,q,s))
    def test_prepared_quant(self):
        c=ctypes.CDLL(str(ROOT/'build/libquant-opt.so'));f=c.test_scalar_descriptor
        f.argtypes=[ctypes.c_int32,ctypes.c_uint64];f.restype=ctypes.c_int8
        rng=random.Random(29)
        for _ in range(10000):
            x=rng.randint(-(1<<31),(1<<31)-1);lo=rng.randint(-128,127);hi=rng.randint(lo,127)
            d=descriptor(rng.randrange(1<<31),rng.randint(-31,0),rng.randint(-128,127),lo,hi)
            self.assertEqual(f(x,d),signed(python_requant(x,d),64))
    def test_categories(self):
        for op,cat in [('xqmac8','custom_mac'),('xrequant8','custom_requant'),('c.fld','floating_point'),('c.lwsp','load'),('c.sdsp','store'),('mulw','multiply'),('c.jr','branch_jump'),('div','divide_remainder'),('csrrs','system'),('addw','integer_ALU')]:self.assertEqual(category(op),cat)
if __name__=='__main__':unittest.main()
