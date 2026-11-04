#!/usr/bin/env python3
"""Export an actual pretrained INT8 MobileNetV3 residual block (ops 14..17)."""
import argparse, collections, hashlib, json, math, struct
from pathlib import Path
import numpy as np
import tflite
from tflite_runtime.interpreter import Interpreter, OpResolverType
ROOT=Path(__file__).resolve().parents[1]
def qm(real):
    f,e=math.frexp(float(real)); q=int(math.floor(f*(1<<31)+0.5))
    if q==1<<31: q//=2; e+=1
    return q,e

def mul(x,q,s):
    x=np.asarray(x,dtype=np.int64)*(1<<max(s,0)); p=x*int(q)
    # SRDHM: signed division truncates towards zero.
    z=p+np.where(p>=0,1<<30,1-(1<<30))
    z=np.where(z>=0,z//(1<<31),-((-z)//(1<<31)))
    r=max(-s,0)
    if r:
        mask=(1<<r)-1
        z=(z>>r)+((z&mask)>((mask>>1)+(z<0)))
    return z

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seed',type=int,default=2026);args=ap.parse_args()
    model=ROOT/'models/mobilenet_v3_large_int8_channelwise.tflite'
    raw=model.read_bytes(); fb=tflite.Model.GetRootAsModel(raw,0); graph=fb.Subgraphs(0)
    rt=Interpreter(model_path=str(model),experimental_preserve_all_tensors=True,num_threads=1,experimental_op_resolver_type=OpResolverType.BUILTIN_REF);rt.allocate_tensors()
    rng=np.random.default_rng(args.seed); inp=rt.get_input_details()[0]
    rt.set_tensor(inp['index'],rng.integers(-128,128,inp['shape'],dtype=np.int8));rt.invoke()
    details={d['index']:d for d in rt.get_tensor_details()}
    def protected_tensor(index):
        # Mark this tensor as a graph output to prevent in-place buffer aliasing.
        buf=bytearray(raw); pos=graph._tab.Vector(graph._tab.Offset(8));struct.pack_into('<i',buf,pos,index)
        r=Interpreter(model_content=bytes(buf),num_threads=1,experimental_op_resolver_type=OpResolverType.BUILTIN_REF)
        r.allocate_tensors();r.set_tensor(inp['index'],rt.get_tensor(inp['index']));r.invoke()
        return r.get_tensor(index)

    def quant(i):
        q=details[i]['quantization_parameters'];return q['scales'].astype(float),q['zero_points'].astype(int)
    arrays={}; params={}; refs={}; x=rt.get_tensor(59)[0].copy(); arrays['block_input']=x
    params['input_zero']=int(quant(59)[1][0]); stats=[]
    for name,opid,ii,wi,bi,oi,dw in [('expand',14,59,214,97,251,False),('depthwise',15,251,215,99,252,True),('project',16,252,216,100,60,False)]:
        w=rt.get_tensor(wi).copy();b=rt.get_tensor(bi).astype(np.int64)
        si,zi=quant(ii);sw,zw=quant(wi);so,zo=quant(oi)
        assert np.all(zw==0)
        qs=[qm(si[0]*v/so[0]) for v in sw]
        op=graph.Operators(opid);opt=tflite.DepthwiseConv2DOptions() if dw else tflite.Conv2DOptions();opt.Init(op.BuiltinOptions().Bytes,op.BuiltinOptions().Pos)
        lo=int(zo[0]) if opt.FusedActivationFunction()==1 else -128
        if dw:
            acc=np.zeros_like(x,dtype=np.int64)+b
            pad=np.pad(x.astype(np.int64)-zi[0],((1,1),(1,1),(0,0)))
            for h in range(3):
                for k in range(3): acc+=pad[h:h+56,k:k+56,:]*w[0,h,k,:]
            macs=56*56*72*9
        else:
            acc=(x.astype(np.int64)-zi[0])@w[:,0,0,:].astype(np.int64).T+b
            macs=int(np.prod(x.shape[:2])*w.shape[0]*w.shape[-1])
        y=np.empty(acc.shape,dtype=np.int8)
        for c,(q,s) in enumerate(qs):y[:,:,c]=np.clip(mul(acc[:,:,c],q,s)+zo[0],lo,127)
        lite=protected_tensor(oi)[0]
        refs[name]=y.copy(); arrays[name+'_w']=w;arrays[name+'_b']=b.astype(np.int32)
        arrays[name+'_mult']=np.array([q for q,s in qs],np.int32);arrays[name+'_shift']=np.array([s for q,s in qs],np.int32)
        params[name]={'input_zero':int(zi[0]),'output_zero':int(zo[0]),'min':lo}
        stats.append({'name':name,'macs':macs,'litert_mismatches':int(np.count_nonzero(y!=lite)),'litert_max_abs_difference':int(np.max(np.abs(y.astype(int)-lite.astype(int))))})
        x=y
    # TFLite reference ADD: common left shift 20 and two input multipliers.
    sa,za=quant(60);sb,zb=quant(59);so,zo=quant(17);common=2*max(sa[0],sb[0])
    aq,ash=qm(sa[0]/common);bq,bsh=qm(sb[0]/common);oq,osh=qm(common/((1<<20)*so[0]))
    x=np.clip(mul(mul((x.astype(np.int64)-za[0])*(1<<20),aq,ash)+mul((arrays['block_input'].astype(np.int64)-zb[0])*(1<<20),bq,bsh),oq,osh)+zo[0],-128,127).astype(np.int8)
    refs['residual']=x
    params['add']={'a_zero':int(za[0]),'b_zero':int(zb[0]),'out_zero':int(zo[0]),'aq':aq,'as':ash,'bq':bq,'bs':bsh,'oq':oq,'os':osh}
    stats.append({'name':'residual','macs':0,'litert_mismatches':int(np.count_nonzero(x!=rt.get_tensor(17)[0])),'litert_max_abs_difference':int(np.max(np.abs(x.astype(int)-rt.get_tensor(17)[0].astype(int))))})
    for n,v in refs.items(): arrays['ref_'+n]=v
    # FC operator from the same model, tested with an actual captured input.
    fc=next(o for o in rt._get_ops_details() if o['op_name']=='FULLY_CONNECTED')
    fi,fw,fbias=map(int,fc['inputs']);fo=int(fc['outputs'][0]);fx=rt.get_tensor(fi).reshape(-1);w=rt.get_tensor(fw);b=rt.get_tensor(fbias)
    si,zi=quant(fi);sw,zw=quant(fw);so,zo=quant(fo);assert np.all(zw==0)
    opt=tflite.FullyConnectedOptions();t=graph.Operators(fc['index']).BuiltinOptions();opt.Init(t.Bytes,t.Pos)
    lo=int(zo[0]) if opt.FusedActivationFunction()==1 else -128
    qs=[qm(si[0]*sw[min(c,len(sw)-1)]/so[0]) for c in range(w.shape[0])]
    ac=(fx.astype(np.int64)-zi[0])@w.astype(np.int64).T+b
    fy=np.array([np.clip(mul(ac[c],q,s)+zo[0],lo,127) for c,(q,s) in enumerate(qs)],dtype=np.int8)
    arrays.update(fc_input=fx,fc_w=w,fc_b=b,fc_mult=np.array([q for q,s in qs],np.int32),fc_shift=np.array([s for q,s in qs],np.int32),ref_fc=fy)
    params['fc']={'input_zero':int(zi[0]),'output_zero':int(zo[0]),'min':lo,'k':w.shape[1],'n':w.shape[0]}
    stats.append({'name':'fc','macs':int(w.size),'litert_mismatches':int(np.count_nonzero(fy!=protected_tensor(fo).reshape(-1)))})
    assert all(z['litert_mismatches']==0 for z in stats), stats
    ops=collections.Counter();model_macs=0;weights=set();float_ops=[]
    for op in rt._get_ops_details():
        typ=op['op_name'];ops[typ]+=1
        if any(details[int(i)]['dtype']==np.float32 for i in list(op['inputs'])+list(op['outputs']) if i>=0):float_ops.append({'index':op['index'],'op':typ})
        if typ in ('CONV_2D','DEPTHWISE_CONV_2D','FULLY_CONNECTED'):
            wi=int(op['inputs'][1]);weights.add(wi);ws=details[wi]['shape'];os=details[int(op['outputs'][0])]['shape']
            model_macs+=int(np.prod(os)*(np.prod(ws[1:]) if typ=='CONV_2D' else np.prod(ws[1:3]) if typ=='DEPTHWISE_CONV_2D' else ws[-1]))
    manifest={'source':'https://huggingface.co/litert-community/MobileNet-v3-large','revision':'9a4fd87358f71befb4de2f5ecdce1a159486b1f2','sha256':hashlib.sha256(raw).hexdigest(),'seed':args.seed,'model_mac_count':model_macs,'weight_elements':sum(int(np.prod(details[i]['shape'])) for i in weights),'operator_counts':dict(ops),'float_boundary_ops':float_ops,'scope':'actual pretrained integer residual block ops 14-17 and first FC; not full-model bare-metal inference','parameters':params,'verification':stats}
    (ROOT/'models/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    out=ROOT/'build/model_data.h';out.parent.mkdir(exist_ok=True)
    with out.open('w') as f:
        f.write('#pragma once\n#include <stdint.h>\n')
        for name,v in arrays.items():
            typ='int8_t' if v.dtype==np.int8 else 'int32_t';flat=v.reshape(-1)
            f.write('static const %s %s[%d] __attribute__((aligned(8))) = {\n'%(typ,name,len(flat)))
            for i in range(0,len(flat),32):f.write(','.join(str(int(z)) for z in flat[i:i+32])+',\n')
            f.write('};\n')
        f.write('#ifdef PREPARED\n')
        for name in ['expand','project','fc']:
            w=arrays[name+'_w'].reshape(len(arrays[name+'_b']),-1).astype(np.int64)
            folded=arrays[name+'_b'].astype(np.int64)-params[name]['input_zero']*w.sum(axis=1)
            assert np.all((folded>=-(1<<31)) & (folded<(1<<31)))
            f.write('static const int32_t %s_folded_b[%d] = {'%(name,len(folded))+','.join(map(str,folded))+'};\n')
        for name in ['expand','depthwise','project','fc']:
            p=params[name];desc=[]
            for q,shift in zip(arrays[name+'_mult'],arrays[name+'_shift']):
                assert 0<=int(q)<(1<<31) and -31<=int(shift)<=0
                desc.append(int(q)|((int(shift)&63)<<32)|((p['output_zero']&255)<<38)|((p['min']&255)<<46)|(127<<54))
            f.write('static const uint64_t %s_desc[%d] = {'%(name,len(desc))+','.join('UINT64_C(%d)'%v for v in desc)+'};\n')
        f.write('#endif\n')
        for name,p in params.items():
            if isinstance(p,dict):
                for k,v in p.items():f.write('#define P_%s_%s (%d)\n'%(name,k,v))
            else:f.write('#define P_%s (%d)\n'%(name,p))
    print(json.dumps(manifest,indent=2))
    # Exact equality to the independent integer reference is tested in C; record runtime rounding differences explicitly.
if __name__=='__main__':main()
