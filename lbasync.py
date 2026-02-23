import logging
import asyncio
import sys
import aiohttp


logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("load_balancer")

HOST = '127.0.0.1'
PORT = 9090

backend_servers = [('127.0.0.1', 8080), ('127.0.0.1', 8081), ('127.0.0.1', 8082)]

healthy_servers = set(backend_servers.copy())
health_check_path = "/health"
state_lock = asyncio.Lock()

rr_index = 0

length_backend_servers = len(backend_servers)
health_check_period = 10 # default 10 seconds

async def read_full_request(client_reader):
  """Read request headers and body from the client.

  Returns (headers_bytes, body_bytes). Bodies are read only when a
  Content-Length header is present; otherwise body_bytes is empty.
  """

  headers = await client_reader.readuntil(b"\r\n\r\n")

  content_length = 0
  try:
    header_text = headers.decode(errors="ignore")
    for line in header_text.split("\r\n"):
      if line.lower().startswith("content-length:"):
        content_length = int(line.split(":", 1)[1].strip() or 0)
        break
  except Exception:
    content_length = 0

  body = b""
  if content_length > 0:
    body = await client_reader.readexactly(content_length)

  return headers, body

async def call_health_route(server):
  url = f"http://{server[0]}:{server[1]}{health_check_path}"

  try:
    async with aiohttp.ClientSession() as session:

      async with session.get(url, timeout=5) as response:
        logger.info(f"Health response from {server}: {response.status}")
        # can access response.headers, body, etc. here if needed for more detailed health checks
      return response.status == 200
  except Exception as e:
    logger.warning("Health check failed for %s: %s", server, e)
    return False

async def updateHealthyServers():
  while (True):
    for server in backend_servers:
      try:
        is_healthy = await call_health_route(server)
        async with state_lock:
          if is_healthy and server not in healthy_servers:
            healthy_servers.add(server)
            logger.info("Server %s marked healthy", server)
          elif not is_healthy and server in healthy_servers:
            healthy_servers.remove(server)
            logger.warning("Server %s marked unhealthy", server)

      except Exception as e:
        logger.exception("Unexpected error during health check for %s", server)
        break

    await asyncio.sleep(health_check_period)

async def find_backend_server():
  global rr_index
  backend_server = None
  async with state_lock:
    if len(healthy_servers) == 0:
      return None
    servers_list = list(healthy_servers)
    servers_list_length = len(servers_list)
  
    rr_index %= servers_list_length
    backend_server = servers_list[rr_index]
    rr_index = (rr_index + 1) % servers_list_length

  return backend_server


async def handle_client(client_reader, client_writer):
  backend_reader = None
  backend_writer = None
  try:
    # find a healthy backend server to route the client's request to
    backend_server =  await find_backend_server()

    if backend_server is None:
      logger.error("No healthy backend available for client")
      client_writer.write(b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
      await client_writer.drain()
      return
    
    logger.info("Routing client to backend %s", backend_server)

    backend_reader, backend_writer = await asyncio.open_connection(backend_server[0], backend_server[1])

    # read only request line + headers from client and forward
    headers, body = await read_full_request(client_reader)

    backend_writer.write(headers)
    if body:
      backend_writer.write(body)
    await backend_writer.drain()
    backend_writer.write_eof() # signal to backend that request is complete

    while True:
      response_chunk = await backend_reader.read(4096)
      if not response_chunk:
        break
      client_writer.write(response_chunk)
      await client_writer.drain()
  except Exception:
    # If anything goes wrong (connect failure, parse error, backend drop), return 502 instead of dropping the socket.
    logger.exception("Request handling failed")
    try:
      client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
      await client_writer.drain()
    except Exception:
      logger.exception("Failed to write 502 response")
  finally:
    client_writer.close()
    await client_writer.wait_closed()
    if backend_writer:
      backend_writer.close()
      await backend_writer.wait_closed()



async def main():
  asyncio.create_task(updateHealthyServers()) # start the health check loop in the background

  server = await asyncio.start_server(handle_client, HOST, PORT) # each client who connects will get their own coroutine to handle the request, allowing for concurrent handling of multiple clients without blocking the main server loop.
  
  async with server: # ensures that the server is properly closed when the main function exits, even if an error occurs. It manages the server's lifecycle, starting it when entering the block and ensuring it is shut down gracefully when exiting.
    await server.serve_forever()


if __name__ == "__main__":
  if len(sys.argv) > 1:
    health_check_period = int(sys.argv[1])
  health_check_period = max(1, health_check_period) 

  asyncio.run(main())


