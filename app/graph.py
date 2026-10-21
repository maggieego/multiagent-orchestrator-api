import os
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END

from app.state import TeamState
from app.config import get_llm
from app.hitl import human_approval_node  # Importado correctamente desde app/hitl.py

# Esquema Pydantic para la salida estructurada del Supervisor
class RouterSchema(BaseModel):
    next_agent: Literal["Investigador", "Analista", "FINISH"] = Field(
        description="El próximo agente que debe actuar o FINISH si la tarea está completada."
    )

async def supervisor_node(state: TeamState) -> dict:
    """Nodo Supervisor: Determina la ruta del flujo basándose en el estado actual y un límite de pasos."""
    messages = state.get("messages", [])
    step_count = state.get("step_count", 0) + 1
    
    # 🚨 Verificamos si ya pasó por el filtro de aprobación humana
    already_approved = state.get("approved_by_human", False)
    
    # 🚨 FORZAR HITL: Solo si es crítico Y TODAVÍA NO HA SIDO APROBADO
    user_query = messages[0].content.lower() if messages else ""
    is_critical_task = any(keyword in user_query for keyword in ["crítico", "critico", "producción", "produccion"])
    
    if is_critical_task and not already_approved:
        return {
            "next_agent": "Analista", 
            "step_count": step_count,
            "is_critical": True  
        }

    # Prevenir bucles infinitos
    if step_count >= 6:
        return {"next_agent": "FINISH", "step_count": step_count}
        
    llm = get_llm()
        
    system_prompt = (
        "Eres el Supervisor de un equipo jerárquico multi-agente. Tu rol es orquestar las tareas.\n"
        "- Delegar al 'Investigador' si falta buscar información de mercado o datos iniciales.\n"
        "- Delegar al 'Analista' si ya hay datos de investigación y se requiere cómputo/métricas cuantitativas.\n"
        "- Responder 'FINISH' cuando el análisis cuantitativo esté completo en el estado."
    )
    
    try:
        structured_llm = llm.with_structured_output(RouterSchema)
        response = await structured_llm.ainvoke([SystemMessage(content=system_prompt)] + messages)
        next_agent = response.next_agent
    except Exception:
        # Fallback determinista defensivo
        if not state.get("research_data"):
            next_agent = "Investigador"
        elif not state.get("analysis_data"):
            next_agent = "Analista"
        else:
            next_agent = "FINISH"
            
    return {"next_agent": next_agent, "step_count": step_count}

async def research_node(state: TeamState) -> dict:
    llm = get_llm()
    last_user_msg = state["messages"][0].content if state.get("messages") else "Investigar oportunidades"
    prompt = f"Como Investigador de Mercado, analiza el siguiente requerimiento y provee datos clave: {last_user_msg}"
    
    res = await llm.ainvoke([HumanMessage(content=prompt)])
    result_text = res.content
    return {
        "research_data": result_text,
        "messages": [AIMessage(content=f"[Investigación]: {result_text}")]
    }

async def analyst_node(state: TeamState) -> dict:
    llm = get_llm()
    research_context = state.get("research_data", "Sin contexto previo")
    prompt = f"Basándote en estos datos de investigación: '{research_context}', calcula las métricas cuantitativas e identificadores de valor correspondientes."
    
    res = await llm.ainvoke([HumanMessage(content=prompt)])
    result_text = res.content
    return {
        "analysis_data": result_text,
        "messages": [AIMessage(content=f"[Análisis]: {result_text}")]
    }

def route_decision(state: TeamState) -> str:
    next_agent = state.get("next_agent")
    if next_agent == "Investigador":
        return "Investigador"
    elif next_agent == "Analista":
        return "AprobacionHumana"
    return END

def build_graph(checkpointer=None):
    workflow = StateGraph(TeamState)
    
    workflow.add_node("Supervisor", supervisor_node)
    workflow.add_node("Investigador", research_node)
    workflow.add_node("AprobacionHumana", human_approval_node)
    workflow.add_node("Analista", analyst_node)
    
    workflow.set_entry_point("Supervisor")
    
    workflow.add_conditional_edges("Supervisor", route_decision, {
        "Investigador": "Investigador",
        "AprobacionHumana": "AprobacionHumana",
        END: END
    })
    
    workflow.add_edge("Investigador", "Supervisor")
    workflow.add_edge("AprobacionHumana", "Analista")
    workflow.add_edge("Analista", "Supervisor")
    
    return workflow.compile(checkpointer=checkpointer)