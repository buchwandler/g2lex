#!/usr/bin/env python3
"""Run a bounded matrix of entry-reduction configurations."""
from __future__ import annotations
import argparse, json
from itertools import product
from pathlib import Path
from .run import run

def main(argv: list[str] | None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--source",default="builtin")
    p.add_argument("--output",type=Path,required=True); p.add_argument("--components",default="2,3,4")
    p.add_argument("--rules",default="concat,compound"); p.add_argument("--optimizer",default="greedy,utility")
    p.add_argument("--data-root",type=Path); p.add_argument("--path",type=Path); a=p.parse_args(argv)
    rows=[]
    for components,rule,optimizer in product((int(v) for v in a.components.split(",")),a.rules.split(","),a.optimizer.split(",")):
        mode="implicit-compound" if rule=="compound" else "implicit-concat"
        dest=a.output/f"{mode}-c{components}-{optimizer}"
        rows.append(run(a.source,mode,dest,data_root=a.data_root,path=a.path,max_components=components,optimizer=optimizer))
    a.output.mkdir(parents=True,exist_ok=True); (a.output/"matrix.json").write_text(json.dumps(rows,indent=2)+"\n",encoding="utf-8")
    return 0
if __name__=="__main__": raise SystemExit(main())
