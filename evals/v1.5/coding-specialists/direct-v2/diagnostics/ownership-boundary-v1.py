"""Post-outcome scoped diagnosis; never revises the frozen scores or artifacts."""
import argparse
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile


def files(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('workspace',type=Path)
    args=parser.parse_args();sys.path.insert(0,str(args.workspace.resolve()))
    templates=importlib.import_module('batchflow.templates')
    runs=importlib.import_module('batchflow.runs')
    rows=[]
    for mode in ['public_put','faulty_producer_missing_options','faulty_producer_with_options']:
        with tempfile.TemporaryDirectory() as directory:
            registry=templates.TemplateRegistry()
            registry.put('alpha',[{'name':'valid','workers':2}])
            store=runs.RunStore(directory,registry)
            good=store.create('alpha')
            before=files(Path(directory))
            record=None;error=None
            bad={'name':'invalid','workers':True}
            if mode.endswith('with_options'):bad['options']={}
            try:
                if mode=='public_put':
                    registry.put('alpha',[bad])
                else:
                    registry.describe=lambda _: {'revision':2,'stages':[deepcopy(bad)],'total_workers':1}
                    record=store.create('alpha')
            except Exception as exc:
                error={'type':type(exc).__name__,'message':str(exc)}
            rows.append({'mode':mode,'rejected':error is not None,'error':error,
                         'persisted_files_unchanged':before==files(Path(directory)),
                         'previous_run_unchanged':store.load(good['run_id'])==good,
                         'returned_workers_type':type(record['stages'][0]['workers']).__name__ if record else None})
    print(json.dumps({'observations':rows,'original_scores_changed':False,'model_calls':0}))


if __name__=='__main__':main()
