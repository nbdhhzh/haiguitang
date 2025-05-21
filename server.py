import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

class RequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/puzzles/'):
            try:
                path = os.path.join('puzzles', unquote(self.path[9:]))
                if not os.path.exists(path):
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'404 Not Found')
                    return
                with open(path, 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain; charset=utf-8')
                    self.send_header('Cache-Control', 'public, max-age=604800')
                    self.end_headers()
                    self.wfile.write(f.read())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f'500 Internal Server Error: {e}'.encode('utf-8'))
        
        elif self.path.startswith('/load-record'):
            try:
                query = urlparse(self.path).query
                params = parse_qs(query)
                puzzle = params.get('puzzle', [''])[0]
                ip = params.get('ip', [''])[0]
                
                record_path = f'records/{puzzle}/{ip}.json'
                if not os.path.exists(record_path):
                    self.send_response(404)
                    self.end_headers()
                    return
                    
                with open(record_path, 'r', encoding='utf-8') as f:
                    record = json.load(f)
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(record).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f'Error loading record: {str(e)}'.encode('utf-8'))
                
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/save-record':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                puzzle = data['puzzle']
                ip = data['ip']
                record_data = data['data']
                
                record_dir = f'records/{puzzle}'
                os.makedirs(record_dir, exist_ok=True)
                
                record_path = f'{record_dir}/{ip}.json'
                with open(record_path, 'w', encoding='utf-8') as f:
                    json.dump(record_data, f, ensure_ascii=False)
                
                self.send_response(200)
                self.end_headers()
                print(f'Record saved successfully')
                self.wfile.write(b'Record saved successfully')
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f'Error saving record: {str(e)}'.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

def run(server_class=HTTPServer, handler_class=RequestHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting server on port {port}...')
    httpd.serve_forever()

if __name__ == '__main__':
    run()
