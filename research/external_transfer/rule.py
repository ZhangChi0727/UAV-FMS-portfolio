"""Import the earlier predictor and extract the original gate without editing its logic."""
import ast
import hashlib
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def pinned(path, sha):
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=sha:
        raise ValueError(f"Unrecognized prior research artifact: {path.name}")
    return data


def module(path,name,sha):
    pinned(path,sha)
    spec=spec_from_file_location(name,path)
    obj=module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


old=module(ROOT/"pubsub_transfer/design.py","prior_design",
           "577db0ee47b4e7bc76bc286e8968d3ceb530a9ab192ce02f00cd5c7eb39f6a81")
scores=old.scores
predict=old.predict
text=pinned(ROOT/"pubsub_transfer/holdback.py",
            "6a820c11e763c7089d3a547f389793f98609d8f859a0798602b41c64bbde875a")
nodes=[n for n in ast.walk(ast.parse(text)) if isinstance(n,ast.Assign)
       and isinstance(n.targets[0],ast.Name) and n.targets[0].id=="use"]
if len(nodes)!=1:
    raise ValueError("Expected exactly one original selective gate")
GATE=compile(ast.Expression(nodes[0].value),"<frozen-holdback-gate>","eval")


def use_field(p):
    return eval(GATE,{"__builtins__":{}},{"p":p})


def label(pred,reference):
    if reference["status"]!="VERIFIED":
        return "no_reference"
    if pred=="UNRESOLVED":
        return "abstain"
    if pred==reference["verdict"]:
        return "correct"
    return "false_pass" if pred=="SAT" else "false_reject"
