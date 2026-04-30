import time
import os
import threading
import psutil
import logging
import random
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, Counter, Gauge, Histogram, REGISTRY

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
logger = logging.getLogger("ProdObservabilityApp")

app = FastAPI(title="ProdObservabilityAPI", version="2.1.0")
BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(BASE_DIR))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus Metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency in seconds', ['method', 'endpoint'])
REQUEST_ERRORS = Counter('http_requests_failed_total', 'Total failed requests', ['method', 'endpoint'])
APP_CPU = Gauge('app_cpu_usage_percent', 'Process CPU usage percent')
APP_MEMORY = Gauge('app_memory_usage_bytes', 'Process memory usage in bytes')
APP_THREADS = Gauge('app_threads_active', 'Active thread count')
APP_DB_POOL = Gauge('app_db_connections_active', 'Simulated active database connections')

@app.middleware("http")
async def metrics_middleware(request, call_next):
    method = request.method
    path = request.url.path
    
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    status_code = response.status_code
    
    REQUEST_COUNT.labels(method=method, endpoint=path, status=status_code).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=path).observe(duration)
    
    if status_code >= 400:
        REQUEST_ERRORS.labels(method=method, endpoint=path).inc()
        logger.warning(f"Error {status_code} on {method} {path} - Duration: {duration:.4f}s")
    else:
        logger.info(f"{method} {path} - Status: {status_code} - Duration: {duration:.4f}s")
        
    return response

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/dashboard")

@app.get("/dashboard")
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/v1/system-state")
async def system_state():
    process = psutil.Process(os.getpid())
    cpu_usage = psutil.cpu_percent()
    mem_usage = process.memory_info().rss
    thread_count = threading.active_count()
    cpu_cores = os.cpu_count()
    db_connections = random.randint(10, 18)
    
    return JSONResponse({
        "cpu_usage": cpu_usage,
        "cpu_cores": cpu_cores,
        "mem_usage": f"{(mem_usage / (1024 * 1024)):.2f}",
        "thread_count": thread_count,
        "db_connections": db_connections,
        "uptime": time.strftime('%Y-%m-%d %H:%M:%S'),
    })

def run_cpu_load(duration, intensity):
    logger.info("Initializing heavy load background worker.")
    end_time = time.time() + duration
    while time.time() < end_time:
        _ = sum([i * i for i in range(intensity)])
    logger.info("Heavy load background worker finished execution.")

@app.get("/api/v1/generate-load")
async def generate_load(background_tasks: BackgroundTasks, duration: int = 15, intensity: int = 50000):
    background_tasks.add_task(run_cpu_load, duration, intensity)
    return {"message": "Load computation initiated"}

@app.get("/api/v1/trigger-error")
async def trigger_error():
    logger.error("Explicit internal exception simulated by diagnostic request")
    raise HTTPException(status_code=500, detail="Observability platform simulated runtime exception.")

@app.get("/metrics", include_in_schema=False)
async def metrics():
    process = psutil.Process(os.getpid())
    APP_CPU.set(psutil.cpu_percent())
    APP_MEMORY.set(process.memory_info().rss)
    APP_THREADS.set(threading.active_count())
    return PlainTextResponse(generate_latest(REGISTRY), media_type="text/plain")