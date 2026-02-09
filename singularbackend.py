import socket

HOST = '127.0.0.1'
PORT = 9090

def handle_client(clientsocket, addr):
    try:
        data_received = clientsocket.recv(4096).decode(errors='replace')
        print(f"Received request from {addr}:\n{data_received}")

        body = "Reply from Backend Server!!"
        resp = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/plain\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n"
            "\r\n"
            f"{body}"
        )
        clientsocket.sendall(resp.encode("utf-8"))


    except Exception as e:
        print(f"Error handling client {addr}: {e}")

    finally:
        clientsocket.close()

def startBEServer():
    socketserver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socketserver.bind((HOST, PORT))
    socketserver.listen(100)

    print(f"Backend Server running on {HOST}:{PORT}")
    try:
      while (1):
        clientsocket, addr = socketserver.accept()
        handle_client(clientsocket, addr)
    except KeyboardInterrupt:
      print("Shutting down backend server .")
    finally:
      socketserver.close()
      




if __name__ == "__main__":
    startBEServer()