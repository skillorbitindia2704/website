# Gunicorn production configuration for Skill Orbit India
import multiprocessing
import os

# Server socket binding
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
backlog = 2048

# Worker processes and threads
# We use multiple threads per worker to efficiently support concurrent 
# chunked LMS video streams and standard API requests.
workers = int(os.getenv("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
threads = 4
worker_class = "gthread"

# Worker timeouts & lifespans
timeout = 120
graceful_timeout = 30
keepalive = 5

# Logging configuration
# Gunicorn binds access and error streams to stderr/stdout for container logger collectors (e.g. Docker, Kubernetes, Render, Heroku)
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" [Tracing-ID: %({X-Request-ID}i)s]'

# Process management
proc_name = "skill_orbit_gunicorn"
daemon = False
pidfile = None
umask = 0o077

# Preload app code for performance and copy-on-write memory sharing
preload_app = True

def on_starting(server):
    server.log.info("Starting production Gunicorn server for Skill Orbit India...")

def post_fork(server, worker):
    server.log.info(f"Worker spawned (PID: {worker.pid})")
