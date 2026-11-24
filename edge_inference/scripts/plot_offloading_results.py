"""Cached-result figures and Markdown tables. No model or replay execution."""
import argparse
import json
from textwrap import fill

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from edge_inference.scripts.run_offloading_experiments import OUTPUT, EDGE, DISCLOSURE

DEST = EDGE/'runs/offloading_figures'
BWS = [1,5,20]
NAMES = dict(fp32_baseline='FP32',pruned_fp32='Pruned FP32',int8='INT8',pruned_int8='Pruned INT8')
COLORS = ['#205993','#ae6430','#66864d','#70437c']
MARKS = ['o','s','D','^']


def accuracy(p, metric):
    a=p['annotation_relative']
    return a['map50'] if metric=='mAP50' else a['per_class']['crack']['recall']


def candidates(g,b):
    return [g['baselines']['all_edge'], next(p for p in g['baselines']['all_cloud']
            if p['config']['bandwidth_mbps']==b), *cgao(g,b)]


def cgao(g,b):
    return [p for p in g['cgao'] if p['config']['bandwidth_mbps']==b]


def frontier(points):
    """Minimize latency and maximize score; collapse ties before dominance."""
    best=float('-inf')
    result=[]
    for x,y in sorted(set(points),key=lambda xy:(xy[0],-xy[1])):
        if y>best:
            result.append((x,y))
            best=y
    return result


def save(fig,name):
    fig.savefig(DEST/f'{name}.svg',facecolor='white')
    fig.savefig(DEST/f'{name}.pdf',facecolor='white')
    fig.savefig(DEST/f'{name}.png',dpi=600,facecolor='white')
    plt.close(fig)


def figures(data):
    DEST.mkdir(exist_ok=True)
    mpl.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],
        'font.size':7,'svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,
        'axes.spines.right':False,'legend.frameon':False,'axes.linewidth':.7})
    handles=[Line2D([],[],marker=m,color=c,linestyle='none',label=n)
             for n,c,m in zip(NAMES.values(),COLORS,MARKS)]
    fig,axes=plt.subplots(4,3,figsize=(7.205,7.36),sharey='row')
    fig.subplots_adjust(left=.11,right=.985,bottom=.153,top=.86,hspace=.58,wspace=.13)
    fig.suptitle('Detection scores versus modeled end-to-end latency',fontsize=13,y=.986)
    fig.legend(handles=handles+[Line2D([],[],color='black',marker='x',linestyle='none',label='All cloud')],
               loc='upper center',bbox_to_anchor=(.5,.956),ncol=5)
    for row,(metric,stat) in enumerate([('mAP50','mean'),('mAP50','p95'),('Crack recall','mean'),('Crack recall','p95')]):
        for j,b in enumerate(BWS):
            ax=axes[row,j]
            xy=[]
            for (v,g),color,mark in zip(data['primary'].items(),COLORS,MARKS):
                for p in candidates(g,b):
                    x=p['summary']['latency_ms'][stat]
                    if x<=0: raise ValueError('nonpositive log-axis latency')
                    y=accuracy(p,metric)
                    xy.append((x,y))
                    policy=p['config']['policy']
                    if policy=='all_cloud':
                        if v=='fp32_baseline': ax.scatter(x,y,c='black',marker='x',s=22)
                    else:
                        ax.scatter(x,y,facecolors=color if policy=='all_edge' else 'none',
                            edgecolors=color,marker=mark,s=20,linewidths=.75)
            fx,fy=zip(*frontier(xy))
            ax.plot(fx,fy,color='#333333',lw=.85,ls='--',zorder=0)
            ax.set_xscale('log')
            ax.set_xlabel(f'{stat.upper()} latency (ms)')
            if j==0: ax.set_ylabel(metric)
            if row==0: ax.set_title(f'{b} Mbps')
            ax.grid(axis='y',alpha=.18)
    fig.text(.05,.089,'Filled: all edge   ·   Open: CGAO (7 thresholds)   ·   Dashed: non-dominated observed points, not interpolation.',fontsize=7)
    fig.text(.05,.055,fill(DISCLOSURE,115),fontsize=7)
    fig.text(.05,.015,'Development-host traces; analytical communication delay. Each point summarizes the same 104 frames.',fontsize=7)
    save(fig,'01-accuracy-latency-frontiers')

    fig,axs=plt.subplots(1,4,figsize=(7.205,3.11))
    fig.subplots_adjust(left=.09,right=.98,top=.70,bottom=.25,wspace=.55)
    fig.suptitle('Confidence gating trades transmission for local compute',fontsize=12,y=.96)
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.88),ncol=4)
    for i,b in enumerate(BWS):
        for (v,g),color,m in zip(data['primary'].items(),COLORS,MARKS):
            ps=cgao(g,b)
            ts=[p['config']['tau'] for p in ps]
            axs[i].plot(ts,[p['summary']['mean_energy_mj'] for p in ps],color=color,marker=m,ms=3,lw=1)
            if i==0:
                axs[3].plot(ts,[100*p['summary']['bandwidth_saving'] for p in ps],color=color,marker=m,ms=3,lw=1)
        axs[i].set_title(f'{b} Mbps')
        axs[i].set_yscale('log')
        es=[p['summary']['mean_energy_mj'] for g in data['primary'].values() for p in g['cgao']]
        if min(es)<=0: raise ValueError('nonpositive log-axis energy')
        axs[i].set_ylim(min(es)/1.2,max(es)*1.2)
    axs[0].set_ylabel('Mean energy (mJ/frame)')
    axs[3].set_ylabel('Bytes saved (%)')
    axs[3].set_title('All bandwidths')
    for ax in axs:
        ax.set_xlabel('Threshold τ')
        ax.set_xticks([.25,.55,.85])
        ax.grid(axis='y',alpha=.2)
    fig.text(.05,.06,'Analytical energy: 10 W compute, 3 W transmit. Full payload; byte savings relative to all cloud. No battery measurements.')
    save(fig,'02-energy-and-byte-savings')


def tables(d):
    def table(header,rows):
        print('| '+' | '.join(header)+' |')
        print('|'+ '|'.join(['---']*len(header))+'|')
        for r in rows: print('| '+' | '.join(map(str,r))+' |')
    print('## Table 1. CPU4 standalone detectors\n\n'+DISCLOSURE+'\n')
    classes=['crack','spallation','corrosion_stain','efflorescence','exposed_bar']
    rows=[]
    for v,g in d['primary'].items():
        a=g['baselines']['all_edge']['annotation_relative']
        rows.append([NAMES[v],f"{a['map50']:.4f}",f"{a['map50_95']:.4f}",
            *[f"{a['per_class'][c]['ap50']:.4f} / {a['per_class'][c]['recall']:.4f}" for c in classes]])
    table(['Model','mAP50','mAP50–95',*[c+' AP50 / recall' for c in classes]],rows)
    print('\n## Table 2. Full-payload analytical replay\n\n'+DISCLOSURE+'\n')
    rows=[]
    for v,g in d['primary'].items():
        for b in BWS:
            for p in candidates(g,b):
                c,s=p['config'],p['summary']
                policy=c['policy']
                if policy=='cgao' and c['tau'] not in [.35,.55,.75]: continue
                if policy=='all_cloud' and v!='fp32_baseline' or policy=='all_edge' and b!=1: continue
                rows.append([NAMES[v] if policy!='all_cloud' else 'shared','all' if policy=='all_edge' else b,
                    policy if policy!='cgao' else f"CGAO {c['tau']:.2f}",f"{s['offload_ratio']:.3f}",
                    f"{s['bandwidth_saving']:.3f}",' / '.join(f"{s['latency_ms'][k]:.1f}" for k in ('mean','p95','p99')),
                    f"{s['mean_energy_mj']:.1f}",f"{accuracy(p,'mAP50'):.4f}",f"{accuracy(p,'Crack recall'):.4f}"])
    table(['Model','Mbps','Policy','ρ','η (bytes)','Mean / P95 / P99 ms','mJ/frame','mAP50','Crack R'],rows)
    print('\n## Table 3. ROI communication sensitivity only\n')
    print('Same gates, 35% of full transmitted bytes; no ROI accuracy/timing measurement. '
          'TX energy saved per submitted frame, not percent total energy.\n')
    rows=[]
    for v,g in d['roi'].items():
        for pf,pr in zip(cgao(d['primary'][v],1),cgao(g,1)):
            s,r=pf['summary'],pr['summary']
            diff=s['transmitted_bytes']-r['transmitted_bytes']
            rows.append([NAMES[v],pf['config']['tau'],f"{s['bandwidth_saving']:.3f} → {r['bandwidth_saving']:.3f}",
                f'{diff/1e6:.2f}',*[f'{3*8*diff/(1000*b*104):.1f}' for b in BWS]])
    table(['Model','τ','η full → ROI','MB saved / 104','TX mJ saved @1','@5','@20'],rows)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['figures','tables'])
    mode=p.parse_args().mode
    data=json.loads(OUTPUT.read_text(encoding='utf-8'))
    (figures if mode=='figures' else tables)(data)
