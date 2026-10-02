from contextlib import contextmanager

from langgraph.checkpoint.sqlite import SqliteSaver

from forge_advisor.config import settings
from forge_advisor.graph.workflow import build_graph


@contextmanager
def graph_runtime():
    settings.ensure_runtime_dirs()
    with SqliteSaver.from_conn_string(settings.checkpoint_db) as checkpointer:
        yield build_graph(checkpointer)
