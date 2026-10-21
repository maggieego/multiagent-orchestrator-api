from typing import TypedDict, Annotated, Optional, List
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class TeamState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    next_agent: Optional[str]
    research_data: Optional[str]
    analysis_data: Optional[str]
    step_count: int
    is_critical: bool
    approved_by_human: Optional[bool]