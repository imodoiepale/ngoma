"""The director engine: a brief becomes a branching production workflow, and grows as you talk.

Nothing in this package generates, spends or publishes on its own. It authors studio
workflows (packages/strategy/workflow_author.py) and hands execution to the runner, which
is gated by run mode and by packages/orchestrator/control.py.
"""
