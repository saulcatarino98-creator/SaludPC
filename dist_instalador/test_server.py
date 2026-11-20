from http.server import HTTPServer, BaseHTTPRequestHandler

class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<h1>Servidor de prueba funcionando</h1><p>Si ves esto, el servidor web funciona correctamente.</p>')
    
    def log_message(self, format, *args):
        print("%s - %s" % (self.address_string(), format % args))

if __name__ == '__main__':
    try:
        server = HTTPServer(('0.0.0.0', 8443), TestHandler)
        print('Servidor de prueba iniciado en puerto 8443')
        print('Prueba en: http://127.0.0.1:8443/')
        print('Presiona Ctrl+C para detener')
        server.serve_forever()
    except Exception as e:
        print(f'Error: {e}')
        input('Presiona Enter para salir...')