import asyncio
import json
import traceback
from langgraph.types import Command
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from app.graph import build_graph
from app.config import get_llm

async def process_task(job_id: str, query: str, is_critical: bool, redis_client, queue_name: str, status_prefix: str, redis_url: str):
    key = f"{status_prefix}{job_id}"
    try:
        await redis_client.set(key, json.dumps({"status": "RUNNING", "result": None}))
        
        # Inicializar el checkpointer con Redis Cloud
        async with AsyncRedisSaver.from_conn_string(redis_url) as checkpointer:
            # Compilar el grafo pasando el checkpointer obligatorio para HITL
            compiled_graph = build_graph(checkpointer=checkpointer)
            
            config = {"configurable": {"thread_id": job_id}}
            initial_state = {
                "messages": [{"role": "user", "content": query}],
                "step_count": 0,
                "is_critical": is_critical,
                "approved_by_human": False
            }
            
            try:
                # Invocación asíncrona del grafo
                result_state = await compiled_graph.ainvoke(initial_state, config=config)
            except Exception as graph_err:
                # LangGraph lanza una excepción controlada al hacer interrupt()
                # Verificamos si el grafo se pausó correctamente
                state_snapshot = await compiled_graph.aget_state(config)
                if state_snapshot.next:
                    await redis_client.set(key, json.dumps({
                        "status": "WAITING_APPROVAL", 
                        "reason": "Requiere aprobación humana antes de ejecutar el análisis.",
                        "thread_id": job_id
                    }))
                    return
                else:
                    raise graph_err

            # Si terminó sin interrupciones
            final_msg = result_state["messages"][-1].content if result_state.get("messages") else "Completado."
            await redis_client.set(key, json.dumps({"status": "DONE", "result": final_msg}))

    except Exception as e:
        error_details = traceback.format_exc()
        await redis_client.set(key, json.dumps({
            "status": "FAILED", 
            "error": str(e),
            "details": error_details
        }))

async def start_worker_loop(redis_client, queue_name: str, status_prefix: str, redis_url: str):
    print("🚀 Worker asíncrono escuchando la cola en Redis Cloud...")
    while True:
        try:
            item = await redis_client.blpop(queue_name, timeout=2)
            if item:
                _, task_json = item
                task_data = json.loads(task_json)
                job_id = task_data["job_id"]
                query = task_data["query"]
                is_critical = task_data.get("is_critical", False)
                
                asyncio.create_task(
                    process_task(job_id, query, is_critical, redis_client, queue_name, status_prefix, redis_url)
                )
        except Exception as e:
            print(f"Error en worker loop: {e}")
            await asyncio.sleep(1)