import asyncio
import httpx
import time

URL = "http://localhost:8000/tasks"

async def send_request(client, i):
    payload = {"query": f"Petición concurrente #{i}: Analizar mercado", "is_critical": False}
    start = time.time()
    try:
        # Configuramos un timeout de 30 segundos para evitar cortes prematuros
        res = await client.post(URL, json=payload, timeout=30.0)
        print(f"Petición {i} encolada exitosamente -> ID: {res.json().get('job_id')} (en {time.time()-start:.2f}s)")
    except Exception as e:
        print(f"Error en petición {i}: {e}")

async def main():
    # Creamos el cliente con timeout explícito
    async with httpx.AsyncClient(timeout=30.0) as client:
        await asyncio.gather(*(send_request(client, i) for i in range(1, 6)))
        print("\n 5 peticiones concurrentes enviadas exitosamente a la cola de Redis.")

if __name__ == "__main__":
    asyncio.run(main())