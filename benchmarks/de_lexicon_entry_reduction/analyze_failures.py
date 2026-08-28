#!/usr/bin/env python3
"""Run offline failure forensics; expected pronunciations never enter runtime assets."""
from __future__ import annotations
import argparse, ast, csv
from pathlib import Path
from lexcompact.asset import load
from lexcompact.diagnostics import analyze_failures, write_diagnostics
from .sources import load_source

def _parse_value(value: str):
    if not value: return None
    try: return ast.literal_eval(value)
    except (SyntaxError, ValueError): return value

def read_failures(path: Path):
    with path.open(encoding='utf-8',newline='') as handle:
        return [{key:_parse_value(value) for key,value in row.items()} for row in csv.DictReader(handle,delimiter='\t')]

def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--source',default='builtin'); p.add_argument('--run',type=Path,required=True)
    p.add_argument('--top-k-segmentations',type=int,default=16); p.add_argument('--boundary-window',type=int,default=3); p.add_argument('--output',type=Path,required=True)
    p.add_argument('--data-root',type=Path); p.add_argument('--path',type=Path); a=p.parse_args(argv)
    source=load_source(a.source,data_root=a.data_root,path=a.path); asset=load(a.run/'candidate.lxc'); fp=a.run/'literal_failures.tsv'; failures=read_failures(fp) if fp.is_file() else []
    result=analyze_failures(source,asset,failures=failures,top_k=a.top_k_segmentations,boundary_window=a.boundary_window); write_diagnostics(a.output,result)
    print(f"analysed {result['baseline_word_count']} words; {result['pronunciation_mismatch_count']} pronunciation mismatches"); return 0
if __name__=='__main__': raise SystemExit(main())
