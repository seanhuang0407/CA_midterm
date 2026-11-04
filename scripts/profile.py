#!/usr/bin/env python3
"""Exact retired-PC histogram classification; no sampling or cycle estimates."""
import argparse,collections,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LOAD={'lb','lbu','lh','lhu','lw','lwu','ld','c.lw','c.ld','c.lwsp','c.ldsp'}
STORE={'sb','sh','sw','sd','c.sw','c.sd','c.swsp','c.sdsp'}
BRANCH={'beq','bne','blt','bge','bltu','bgeu','jal','jalr','c.j','c.jal','c.jr','c.jalr','c.beqz','c.bnez'}
def category(op):
    if op=='xqmac8':return 'custom_mac'
    if op=='xrequant8':return 'custom_requant'
    if op.startswith(('c.fl','c.fs')):return 'floating_point'
    if op in LOAD:return 'load'
    if op in STORE:return 'store'
    if op in BRANCH:return 'branch_jump'
    if op.startswith('mul'):return 'multiply'
    if op.startswith(('div','rem')):return 'divide_remainder'
    if op.startswith(('csr','ecall','ebreak','wfi','fence')):return 'system'
    if op.startswith('f') and not op.startswith('fence'):return 'floating_point'
    return 'integer_ALU'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--variant',required=True);a=ap.parse_args();v=a.variant
    dis=(ROOT/f'build/{v}.dis').read_text();inst={};symbols=[]
    for line in dis.splitlines():
        m=re.match(r'^\s*([0-9a-f]+):\s+([0-9a-f]+)\s+(\S+)',line)
        if m:
            bits=int(m[2],16);op=m[3]
            if bits&0xfe00707f==0x0b:op='xqmac8'
            elif bits&0xfe00707f==0x100b:op='xrequant8'
            inst[int(m[1],16)]=(op,len(m[2])//2)
    for line in (ROOT/f'build/{v}.symbols').read_text().splitlines():
        t=line.split()
        if len(t)==4 and t[2] in ('t','T'):symbols.append((int(t[0],16),int(t[1],16),t[3]))
    mix=collections.Counter();fcounts=collections.Counter();work=collections.Counter();wmn=collections.Counter();total=0;unknown=0
    for line in (ROOT/f'results/{v}.histogram').read_text().splitlines():
        m=re.fullmatch(r'([0-9a-f]+) (\d+)',line)
        if not m:continue
        pc,n=int(m[1],16),int(m[2]);total+=n
        if pc not in inst:unknown+=n;continue
        op=inst[pc][0];cls=category(op);mix[cls]+=n
        fn=next((name for start,size,name in symbols if start<=pc<start+size),'unknown')
        fcounts[fn]+=n
        if fn in ('pointwise','depthwise','residual','qmul','requant','pointwise_prepared','depthwise_prepared'):
            work[cls]+=n;wmn[op]+=n
    out=(ROOT/f'results/{v}.stdout').read_text();roi={n:int(c) for n,c in re.findall(r'ROI (\w+) instret=(\d+)',out)}
    macs={'expand':5419008,'depthwise':2032128,'project':5419008,'residual':0,'fc':1228800,'micro':128}
    den=sum(roi.values());mac=sum(macs[n] for n in roi)
    code_bytes=sum(size for op,size in inst.values())
    result={'variant':v,'measurement':'Spike exact retired PC histogram; CSR minstret operator intervals','whole_program_retired':total,'unknown_pc_retired':unknown,'whole_program_instruction_mix':dict(mix),'kernel_instruction_mix':dict(work),'kernel_mnemonics':dict(wmn),'function_retired':dict(fcounts),'operator_instret':roi,'operator_share':{k:n/den for k,n in roi.items()},'ROI_retired':den,'ROI_MACs':mac,'ROI_MAC_per_instruction':mac/den,'kernel_memory_instructions':work['load']+work['store'],'kernel_load_store_per_MAC':(work['load']+work['store'])/mac,'disassembled_text_bytes':code_bytes,'custom_instruction_frequency':(work['custom_mac']+work['custom_requant'])/sum(work.values()),'custom_instruction_counts':{'xqmac8':work['custom_mac'],'xrequant8':work['custom_requant']},'custom_MAC_coverage':8*work['custom_mac']/mac,'functional_pass':out.rstrip().endswith('PASS')}
    outputs={'expand':225792,'depthwise':225792,'project':75264,'residual':75264,'fc':1280,'micro':1}
    result['operator_instructions_per_output']={name:count/outputs[name] for name,count in roi.items()}
    assert result['functional_pass'];assert not work['floating_point']
    assert sum(mix.values())+unknown==total
    if v in ('X1','X2','micro-X1','micro-X2'):assert work['custom_mac']>0
    if v in ('XR','X2','micro-XR','micro-X2'):assert work['custom_requant']>0
    if v in ('B0','B1','S','P','micro','micro-S','micro-P'):assert not (work['custom_mac']+work['custom_requant'])
    expected_mac=16 if 'micro' in v else 1508352
    expected_req=1 if 'micro' in v else 528128
    assert work['custom_mac']==(expected_mac if v in ('X1','X2','micro-X1','micro-X2') else 0)
    assert work['custom_requant']==(expected_req if v in ('XR','X2','micro-XR','micro-X2') else 0)
    (ROOT/f'results/{v}.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
