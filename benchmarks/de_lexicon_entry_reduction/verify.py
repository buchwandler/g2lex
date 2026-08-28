#!/usr/bin/env python3
"""Independently verify a benchmark candidate against a source."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from lexcompact.asset import load
from lexcompact.verify import verify_candidate
from .sources import load_source

def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run",type=Path,required=True); p.add_argument("--source",default="builtin")
    p.add_argument("--data-root",type=Path); p.add_argument("--path",type=Path)
    a=p.parse_args(argv)
    baseline=load_source(a.source,data_root=a.data_root,path=a.path)
    candidate=load(a.run/"candidate.lxc")
    result=verify_candidate(candidate,baseline)
    (a.run/"verification.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2)); return 0 if result["lossless"] else 1
if __name__=="__main__": raise SystemExit(main())
