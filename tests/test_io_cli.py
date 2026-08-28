import json
from pathlib import Path
from lexcompact.asset import load
from lexcompact.cli import main
from lexcompact.io import read_lexicon


def test_json_cli_roundtrip(tmp_path: Path):
    source=tmp_path/"lexicon.json"; source.write_text(json.dumps({"a":"x","b":"y","ab":"xy"}),encoding="utf-8")
    asset=tmp_path/"lexicon.lxc"; report=tmp_path/"report.json"
    assert main(["reduce",str(source),str(asset),"--report",str(report)])==0; assert main(["verify",str(source),str(asset)])==0
    loaded=load(asset); assert loaded.literal_word_count==2; assert loaded.generated_word_count==1; assert loaded.get("ab")=="xy"
    restored=tmp_path/"restored.json"; assert main(["restore",str(asset),str(restored),"--format","json"])==0
    assert read_lexicon(restored).entries==read_lexicon(source).entries; assert json.loads(report.read_text())["lossless"]


def test_tsv_duplicate_variants(tmp_path: Path):
    source=tmp_path/"lexicon.tsv"; source.write_text("A\tx\nA\tq\nB\ty\nAB\txy\nAB\tqy\n",encoding="utf-8")
    asset=tmp_path/"lexicon.lxc"; assert main(["reduce",str(source),str(asset),"--format","tsv"])==0
    assert load(asset).lookup_all("AB")== ("xy","qy")
