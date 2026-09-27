from .runs import render_manifest


def show_run(store, run_id):
    return render_manifest(store.load(run_id))
