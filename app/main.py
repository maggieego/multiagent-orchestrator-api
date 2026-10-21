import os
from dotenv import load_dotenv

# 🔑 Cargamos las variables del archivo .env al entorno de Python
load_dotenv()

import uuid
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from langgraph.checkpoint.memory import MemorySaver

from app.graph import build_graph

app = FastAPI(title="Multiagent Orchestrator API - Coderhouse")

# Usamos MemorySaver
memory = MemorySaver()
compiled_graph = build_graph(checkpointer=memory)

class TaskRequest(BaseModel):
    query: str

async def run_initial_graph(job_id: str, initial_state: dict):
    """Ejecuta el grafo inicialmente en segundo plano hasta el interrupt o fin."""
    config = {"configurable": {"thread_id": job_id}}
    try:
        await compiled_graph.ainvoke(initial_state, config=config)
    except Exception as e:
        print(f"Error en ejecución inicial del job {job_id}: {str(e)}")

@app.post("/tasks")
async def create_task(task: TaskRequest, background_tasks: BackgroundTasks):
    """Crea e inicia una nueva tarea multi-agente en segundo plano para evitar bloqueos y timeouts."""
    job_id = str(uuid.uuid4())
    
    initial_state = {
        "messages": [{"role": "user", "content": task.query}],
        "step_count": 0,
        "research_data": "",
        "analysis_data": "",
        "approved_by_human": False,
        "is_critical": False
    }
    
    # 🚀 Delegamos la ejecución inicial a segundo plano para soportar alta concurrencia
    background_tasks.add_task(run_initial_graph, job_id, initial_state)
        
    return {"job_id": job_id, "status": "started"}

@app.get("/tasks/{job_id}")
async def get_task_status(job_id: str):
    """Consulta el estado actual del job, detectando si está en ejecución, esperando aprobación o finalizado."""
    config = {"configurable": {"thread_id": job_id}}
    
    try:
        state_snapshot = compiled_graph.get_state(config)
    except Exception:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    status = "RUNNING"
    
    # 🔍 Verificamos si el grafo está pausado esperando el nodo HITL (AprobacionHumana)
    if state_snapshot.next and "AprobacionHumana" in state_snapshot.next:
        status = "WAITING_APPROVAL"
    elif not state_snapshot.next and state_snapshot.values:
        status = "DONE"
        
    return {
        "job_id": job_id,
        "status": status,
        "values": state_snapshot.values
    }

async def resume_graph_task(job_id: str):
    """Función auxiliar que reanuda el grafo en segundo plano para evitar bloqueos HTTP."""
    from langgraph.types import Command
    config = {"configurable": {"thread_id": job_id}}
    try:
        await compiled_graph.ainvoke(
            Command(resume={"approved": True}), 
            config=config
        )
    except Exception as e:
        print(f"Error al procesar la tarea reanudada en segundo plano {job_id}: {str(e)}")

@app.post("/tasks/{job_id}/approve")
async def approve_task(job_id: str, background_tasks: BackgroundTasks):
    """Reanuda la ejecución del grafo de forma asíncrona mediante BackgroundTasks."""
    config = {"configurable": {"thread_id": job_id}}
    
    try:
        state_snapshot = compiled_graph.get_state(config)
        if not state_snapshot.next:
            raise HTTPException(status_code=400, detail="El job no está pausado o ya finalizó.")
        
        background_tasks.add_task(resume_graph_task, job_id)
        
        return {
            "status": "success", 
            "message": "Aprobación registrada. La tarea continúa ejecutándose en segundo plano."
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo aprobar la tarea: {str(e)}")