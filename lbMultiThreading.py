import logging
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
import sys
import time

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("load_balancer")

HOST = '127.0.0.1'
PORT = 9090
thread_pool_workers = 50

backend_servers = [('127.0.0.1', 8080), ('127.0.0.1', 8081), ('127.0.0.1', 8082)]

healthy_servers = set(backend_servers.copy())
health_check_path = "/health"
health_lock = threading.Lock()

rr_index = 0
rr_lock = threading.Lock()

length_backend_servers = len(backend_servers)
health_check_period = 10 # default 10 seconds

def call_health_route(server):
  sock = None
  try:
    request = f"GET {health_check_path} HTTP/1.1\r\nHost: {server[0]}\r\nConnection: close\r\n\r\n"

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(server)
    sock.sendall(request.encode())

    response = sock.recv(4096).decode()
    logger.debug("Health response from %s: %s", server, response.splitlines()[0] if response else "<empty>")
    return "200 OK" in response
  except Exception as e:
    logger.warning("Health check failed for %s: %s", server, e)
    return False
  finally:
    if sock:
      sock.close()

def updateHealthyServers():
  while (True):
    for server in backend_servers:
      try:
        is_healthy = call_health_route(server)
        with health_lock:
          if is_healthy and server not in healthy_servers:
            healthy_servers.add(server)
            logger.info("Server %s marked healthy", server)
          elif not is_healthy and server in healthy_servers:
            healthy_servers.remove(server)
            logger.warning("Server %s marked unhealthy", server)

      except Exception as e:
        logger.exception("Unexpected error during health check for %s", server)

    time.sleep(health_check_period)

def find_backend_server():
  global rr_index
  backend_server = None

  with health_lock:
    if len(healthy_servers) == 0:
      return None
    servers_list = list(healthy_servers)
    servers_list_length = len(servers_list)
  
  rr_lock.acquire()
  try:
      rr_index %= servers_list_length
      backend_server = servers_list[rr_index]
      rr_index = (rr_index + 1) % servers_list_length
  finally:
    rr_lock.release()
  return backend_server


def handle_client(clientsocket, addr):
  backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  try:
    data_received = clientsocket.recv(4096)

    backend_server = find_backend_server()
    if backend_server is None:
      logger.error("No healthy backend available for client %s", addr)
      clientsocket.sendall(b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
      return
    logger.info("Routing client %s to backend %s", addr, backend_server)
    
    backend_socket.connect(backend_server)
    backend_socket.sendall(data_received)
    while (1):
      chunk = backend_socket.recv(4096)
      if not chunk:
        break
      clientsocket.sendall(chunk)
  except Exception as e:
    logger.exception("Error handling client %s", addr)

  finally:
    if (clientsocket):
      clientsocket.close()
    if (backend_socket):
      backend_socket.close()



def startMultiThreadServer():
  serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  serversocket.bind((HOST, PORT))
  serversocket.listen(100) #tells the Operating System how many unaccepted connections to keep in a queue before it starts refusing new people

  logger.info("Load Balancer Server running on %s:%s", HOST, PORT)
  executor = ThreadPoolExecutor(max_workers=thread_pool_workers)

  try:
    while (1):
      clientsocket, addr = serversocket.accept()
      logger.debug("Accepted connection from %s", addr)

      executor.submit(handle_client, clientsocket, addr)
  
  except KeyboardInterrupt:
    logger.info("Shutting down the load balancer server")
  finally:
    serversocket.close()
    executor.shutdown(wait=True)


if __name__ == "__main__":
  if len(sys.argv) > 1:
    health_check_period = int(sys.argv[1])
  health_check_period = max(1, health_check_period) 
  health_check_thread = threading.Thread(target=updateHealthyServers, daemon=True)
  health_check_thread.start()

  startMultiThreadServer()



