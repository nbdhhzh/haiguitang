import os
import json
from flask import Flask, request, Response, abort, send_from_directory

app = Flask(__name__)

# 确保 'records' 和 'puzzles' 目录存在
os.makedirs('records', exist_ok=True)
os.makedirs('static/puzzles', exist_ok=True)

@app.route('/puzzles', methods=['GET'])
def get_all_puzzles():
    """
    Returns all puzzles in JSON format: {filename: content}
    """
    puzzles = {}
    for filename in os.listdir('static/puzzles'):
        if filename.endswith('.md'):
            with open(os.path.join('static/puzzles', filename), 'r', encoding='utf-8') as f:
                puzzles[filename] = f.read()
    
    resp = Response(json.dumps(puzzles, ensure_ascii=False).encode('utf-8'), status=200)
    resp.headers['Content-type'] = 'application/json'
    return resp

@app.route('/puzzles/<path:subpath>', methods=['GET'])
def get_puzzle(subpath):
    """
    Handles GET requests for /puzzles/<path:subpath>
    Serves static puzzle files from the 'puzzles' directory with specific headers.
    """
    try:
        # 模拟原始行为：直接拼接路径，然后打开文件
        file_path = os.path.join('static/puzzles', subpath)
        
        # 确保路径是安全的，防止目录遍历攻击 (虽然send_from_directory更安全，这里手动模拟)
        # 这是一个简单的检查，更严谨的生产环境应使用 werkzeug.utils.safe_join
        if not os.path.normpath(file_path).startswith(os.path.normpath('static/puzzles')):
            abort(403) # Forbidden

        if not os.path.exists(file_path):
            # 模拟原始的 404 响应
            resp = Response(b'404 Not Found', status=404)
            return resp
        with open(file_path, 'rb') as f:
            content = f.read()
            # 模拟原始的 200 响应和头部信息
            resp = Response(content, status=200)
            resp.headers['Content-type'] = 'text/plain; charset=utf-8'
            resp.headers['Cache-Control'] = 'public, max-age=604800'
            return resp
    except Exception as e:
        # 模拟原始的 500 响应
        resp = Response(f'500 Internal Server Error: {e}'.encode('utf-8'), status=500)
        return resp

@app.route('/load-record', methods=['GET'])
def load_record():
    """
    Handles GET requests for /load-record
    Loads and returns a JSON record based on 'puzzle' and 'userId' query parameters.
    If puzzle is not specified, returns all records for the user.
    """
    puzzle = request.args.get('puzzle')
    userId = request.args.get('userId')

    if not os.path.exists('records'):
        os.makedirs('records')
    record_path = os.path.join('records', f'{userId or ""}.json')
    try:
        if not os.path.exists(record_path):
            with open(record_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            
        with open(record_path, 'r', encoding='utf-8') as f:
            user_records = json.load(f)
            
            # 如果没有指定puzzle，返回全部记录
            if not puzzle:
                json_content = json.dumps(user_records, ensure_ascii=False).encode('utf-8')
            else:
                record = user_records.get(puzzle + ".md")
                if not record:
                    resp = Response(status=404)
                    return resp
                json_content = json.dumps(record, ensure_ascii=False).encode('utf-8')
            
            # 模拟原始的 200 响应和头部信息
            resp = Response(json_content, status=200)
            resp.headers['Content-type'] = 'application/json'
            return resp
    except Exception as e:
        # 模拟原始的 500 响应
        resp = Response(f'Error loading record: {str(e)}'.encode('utf-8'), status=500)
        return resp

@app.route('/save-record', methods=['POST'])
def save_record():
    """
    Handles POST requests for /save-record
    Saves a JSON record received in the request body.
    """
    try:
        # 模拟原始代码的 content_length 读取，但 Flask 推荐 get_json()
        # 这里为了确保完全一致，我们用 request.data (原始字节流) 来模拟原始的 self.rfile.read
        # 然后手动解析 JSON
        post_data = request.data
        if not post_data: # 原始代码在没有数据时会引发 JSONDecodeError
             raise json.JSONDecodeError("Expecting value", "", 0)

        data = json.loads(post_data.decode('utf-8'))
        
        # 原始代码没有对 data 的结构进行严格检查，而是直接访问键
        # 如果键不存在，会引发 KeyError，然后被外层 except 捕获
        puzzle = data['puzzle'] + '.md'
        userId = data['userId']
        record_data = data['data']
        
        # 每个用户一个json文件，内部按题目存储
        record_path = os.path.join('records', f'{userId}.json')
        user_records = {}
        
        # 如果文件已存在，先读取现有记录
        if os.path.exists(record_path):
            with open(record_path, 'r', encoding='utf-8') as f:
                user_records = json.load(f)
        
        # 更新或添加当前题目的记录
        user_records[puzzle] = record_data
        
        # 写入更新后的记录
        with open(record_path, 'w', encoding='utf-8') as f:
            json.dump(user_records, f, ensure_ascii=False, indent=2)
        
        # 模拟原始的 200 响应
        resp = Response(b'Record saved successfully', status=200)
        return resp
    except Exception as e:
        # 模拟原始的 500 响应
        resp = Response(f'Error saving record: {str(e)}'.encode('utf-8'), status=500)
        return resp

# Fallback for other static files (similar to SimpleHTTPRequestHandler's default behavior)
# 这部分使用 Flask 内置的 send_from_directory 更安全和方便
# 原始代码中 SimpleHTTPRequestHandler 的 do_GET 默认行为
# 实际上是直接服务当前目录下的文件，这里也尽量模拟
@app.route('/<path:filename>', methods=['GET'])
def serve_static(filename):
    """
    Serves any other static files from the root directory.
    """
    try:
        return send_from_directory('.', filename)
    except FileNotFoundError:
        resp = Response(b'404 Not Found', status=404)
        return resp
    except Exception as e:
        resp = Response(f'500 Internal Server Error: {e}'.encode('utf-8'), status=500)
        return resp

@app.route('/', methods=['GET'])
def index():
    """
    Serves the index.html file from the root directory if requested.
    """
    try:
        return send_from_directory('.', 'index.html')
    except FileNotFoundError:
        resp = Response(b'404 Not Found', status=404)
        return resp
    except Exception as e:
        resp = Response(f'500 Internal Server Error: {e}'.encode('utf-8'), status=500)
        return resp

@app.errorhandler(404)
def not_found_error(error):
    # 模拟原始代码中 do_POST 针对其他路径的 404 响应
    # do_GET 的其他路径已经通过 serve_static 模拟
    if request.path == '/save-record' and request.method == 'POST':
        return Response(b'Not Found', status=404)
    return error.original_response or Response(b'404 Not Found', status=404) # 默认的 404

# 运行 Flask 应用
if __name__ == '__main__':
    print("Starting Flask server on port 8080...")
    app.run(host='0.0.0.0', port=8080, debug=True) # 在生产环境中请关闭 debug=True
