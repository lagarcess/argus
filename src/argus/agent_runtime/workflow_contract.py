from __future__ import annotations

from enum import Enum


class WorkflowNode(str, Enum):
    INTERPRET = "interpret"
    CLARIFY = "clarify"
    CONFIRM = "confirm"
    EXECUTE = "execute"
    EXPLAIN = "explain"
    NEXT_STEP = "next_step"


TOKEN_STREAM_NODES = frozenset(
    {
        WorkflowNode.CLARIFY.value,
        WorkflowNode.EXPLAIN.value,
        WorkflowNode.NEXT_STEP.value,
    }
)
WORKFLOW_NODE_NAMES = frozenset(node.value for node in WorkflowNode)
