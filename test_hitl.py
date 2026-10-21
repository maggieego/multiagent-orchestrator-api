import time
import httpx

BASE_URL = "http://127.0.0.1:8000/tasks"

def test_hitl_workflow():
    print("1. Enviando tarea CRÍTICA (debe pausarse en HITL)...")
    payload = {
        "query": "Ejecutar despliegue CRÍTICO en producción con aprobación requerida"
    }
    
    # ⏱️ Agregado timeout de 120 segundos para la creación inicial de la tarea
    response = httpx.post(BASE_URL, json=payload, timeout=120.0)
    job_id = response.json().get("job_id")
    print(f"   -> Job ID creado: {job_id}")
    
    print("2. Esperando a que el worker procese y pause en el interrupt...")
    status = "RUNNING"
    max_retries = 15
    attempts = 0
    
    while status == "RUNNING" and attempts < max_retries:
        time.sleep(2)
        status_res = httpx.get(f"{BASE_URL}/{job_id}")
        data = status_res.json()
        status = data.get("status")
        print(f"   -> Estado actual: {status}")
        attempts += 1
        
    if status != "WAITING_APPROVAL":
        print(f"❌ La tarea terminó con estado inesperado: {status}")
        exit(1)
        
    print("3. ¡Tarea pausada con éxito! Aprobando la tarea mediante el endpoint...")
    # ⏱️ Agregado timeout de 120 segundos para la aprobación y reanudación del grafo
    approval_res = httpx.post(f"{BASE_URL}/{job_id}/approve", timeout=120.0)
    print(f"   -> Respuesta de aprobación: {approval_res.json()}")
    
    print("¡Flujo HITL completado exitosamente!")

if __name__ == "__main__":
    test_hitl_workflow()