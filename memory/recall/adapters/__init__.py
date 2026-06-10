"""Framework adapters for Recall.

* ``RecallMemory`` — framework-agnostic core (always available).
* ``recall_nodes`` — LangGraph retrieve/ingest nodes.
* ``build_recall_memory`` — LangChain ``BaseMemory`` (needs langchain-core).
* ``build_autogen_memory`` — AutoGen ``Memory`` (needs autogen-core).

The framework-specific builders import their frameworks lazily, so importing this
package never requires LangGraph/LangChain/AutoGen to be installed.
"""

from recall.adapters.base import RecallMemory

__all__ = ["RecallMemory", "recall_nodes", "build_recall_memory", "build_autogen_memory"]


def recall_nodes(*args, **kwargs):
    from recall.adapters.langgraph_adapter import recall_nodes as _f

    return _f(*args, **kwargs)


def build_recall_memory(*args, **kwargs):
    from recall.adapters.langchain_adapter import build_recall_memory as _f

    return _f(*args, **kwargs)


def build_autogen_memory(*args, **kwargs):
    from recall.adapters.autogen_adapter import build_autogen_memory as _f

    return _f(*args, **kwargs)
