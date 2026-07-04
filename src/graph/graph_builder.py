"""Assembles all agent nodes into the LangGraph StateGraph."""
import sys

from langgraph.graph import END, StateGraph

from agents.approval_agent import human_approval
from agents.architecture_agent import architecture_agent
from agents.coding_agent import coding_agent
from agents.debug_agent import debug_agent
from agents.execution_agent import execution_agent
from agents.memory_updater import memory_updater
from agents.planner_agent import planner_agent
from agents.requirement_agent import requirement_agent
from agents.review_agent import review_agent
from agents.test_agent import test_agent
from exception import MyException
from graph.routing import route_after_approval, route_after_execution, route_after_review
from graph.state import GraphState
from logger import GLOBAL_LOGGER as logger


def build_graph():
    try:
        graph = StateGraph(GraphState)

        graph.add_node("requirement_agent", requirement_agent)
        graph.add_node("architecture_agent", architecture_agent)
        graph.add_node("task_planner", planner_agent)
        graph.add_node("coding_agent", coding_agent)
        graph.add_node("test_agent", test_agent)
        graph.add_node("execution_agent", execution_agent)
        graph.add_node("debug_agent", debug_agent)
        graph.add_node("review_agent", review_agent)
        graph.add_node("human_approval", human_approval)
        graph.add_node("memory_updater", memory_updater)

        graph.set_entry_point("requirement_agent")
        graph.add_edge("requirement_agent", "architecture_agent")
        graph.add_edge("architecture_agent", "task_planner")
        graph.add_edge("task_planner", "coding_agent")
        graph.add_edge("coding_agent", "test_agent")
        graph.add_edge("test_agent", "execution_agent")

        graph.add_conditional_edges(
            "execution_agent",
            route_after_execution,
            {"review_agent": "review_agent", "debug_agent": "debug_agent"},
        )
        graph.add_edge("debug_agent", "execution_agent")

        graph.add_conditional_edges(
            "review_agent",
            route_after_review,
            {"human_approval": "human_approval", "coding_agent": "coding_agent"},
        )

        graph.add_conditional_edges(
            "human_approval",
            route_after_approval,
            {"memory_updater": "memory_updater", "coding_agent": "coding_agent"},
        )

        graph.add_edge("memory_updater", END)

        compiled = graph.compile()
        logger.info("graph_built")
        return compiled
    except Exception as e:
        logger.error("graph_build_failed", error=str(e))
        raise MyException(e, sys) from e
