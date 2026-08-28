#!/usr/bin/env python3
"""Measure fresh-process baseline/candidate load and lookup costs."""
from __future__ import annotations
import argparse, json, platform, resource, subprocess, sys, time
from pathlib import Path

def rss_bytes()->int:
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if platform.system()=="Darwin" else value*1024)

def _worker(kind:str,run:Path,source:str,data_root:Path|None,path:Path|None)->None:
    before=rss_bytes(); started=time.perf_counter()
    if kind=="candidate":
        from lexcompact.asset import load
        load(run/"candidate.lxc")
    else:
        from .sources import load_source
        load_source(source,data_root=data_root,path=path)
    print(json.dumps({"rss_delta_bytes":rss_bytes()-before,"cold_load_ms":(time.perf_counter()-started)*1000}))

def _lookup_metrics(run:Path)->dict[str,object]:
    from lexcompact.asset import load
    from lexcompact.verify import adversarial_misses
    candidate=load(run/"candidate.lxc"); all_words=candidate.membership.iter_words(); literal_words=set(candidate.literals)
    generated=tuple(w for w in all_words if w not in literal_words); misses=adversarial_misses(all_words); metrics={}
    for name,words in (("literal",tuple(candidate.literals)),("generated",generated),("miss",misses)):
        sample=words[:1000]; started=time.perf_counter(); durations=[]
        for word in sample:
            one=time.perf_counter_ns(); candidate.lookup_all(word); durations.append((time.perf_counter_ns()-one)/1_000_000)
        elapsed=time.perf_counter()-started; metrics[f"{name}_lookup_words_per_second"]=(len(sample)/elapsed if elapsed else 0.0)
        if name=="generated" and durations:
            ordered=sorted(durations)
            for q in (50,95,99): metrics[f"generated_lookup_p{q}_ms"]=ordered[min(len(ordered)-1,len(ordered)*q//100)]
    return metrics

def benchmark(run:Path,*,source:str="builtin",data_root:Path|None=None,path:Path|None=None)->dict[str,object]:
    values={}
    for kind in ("baseline","candidate"):
        command=[sys.executable,"-m","benchmarks.de_lexicon_entry_reduction.benchmark_memory","--worker",kind,"--run",str(run),"--source",source]
        if data_root: command.extend(("--data-root",str(data_root)))
        if path: command.extend(("--path",str(path)))
        completed=subprocess.run(command,check=True,capture_output=True,text=True); values[kind]=json.loads(completed.stdout)
    baseline=values["baseline"]; candidate=values["candidate"]; br=int(baseline["rss_delta_bytes"]); cr=int(candidate["rss_delta_bytes"])
    result={"baseline_rss_delta_bytes":br,"candidate_rss_delta_bytes":cr,"rss_saved_bytes":br-cr,
            "rss_reduction_rate":((br-cr)/br if br else 0.0),"baseline_cold_load_ms":baseline["cold_load_ms"],
            "candidate_cold_load_ms":candidate["cold_load_ms"]}
    result.update(_lookup_metrics(run)); return result

def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--run",type=Path,required=True); p.add_argument("--source",default="builtin")
    p.add_argument("--data-root",type=Path); p.add_argument("--path",type=Path); p.add_argument("--output",type=Path); p.add_argument("--worker",choices=("baseline","candidate")); a=p.parse_args(argv)
    if a.worker: _worker(a.worker,a.run,a.source,a.data_root,a.path); return 0
    result=benchmark(a.run,source=a.source,data_root=a.data_root,path=a.path); destination=a.output or a.run/"runtime.json"
    destination.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8"); print(json.dumps(result,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
