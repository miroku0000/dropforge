"""
Remote Control Server for eBay Automation System
Access from Claude app on phone via browser
"""

from flask import Flask, render_template_string, jsonify, request, send_file, redirect
import subprocess
import os
import json
import threading
import time
from datetime import datetime
import psutil
import glob
from ebay_oauth_helper import eBayOAuthHelper, auto_refresh_token

app = Flask(__name__)
oauth_helper = eBayOAuthHelper()

# Store running processes
running_processes = {}
process_logs = {}

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>eBay Automation Control</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 28px;
        }
        .card {
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .card h2 {
            color: #333;
            margin-bottom: 15px;
            font-size: 20px;
        }
        .button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 25px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            margin-bottom: 10px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .button:active {
            transform: scale(0.98);
        }
        .button:hover {
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        .button.danger {
            background: linear-gradient(135deg, #f35b57 0%, #d63031 100%);
        }
        .button.success {
            background: linear-gradient(135deg, #00b894 0%, #00cec9 100%);
        }
        .button.warning {
            background: linear-gradient(135deg, #fdcb6e 0%, #f39c12 100%);
        }
        .status {
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 10px;
            font-size: 14px;
        }
        .status.running {
            background: #d4edda;
            color: #155724;
        }
        .status.stopped {
            background: #f8d7da;
            color: #721c24;
        }
        .log-output {
            background: #f1f3f4;
            padding: 10px;
            border-radius: 5px;
            font-family: monospace;
            font-size: 12px;
            max-height: 200px;
            overflow-y: auto;
            margin-top: 10px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 15px;
        }
        .stat-box {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }
        .stat-label {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        select {
            width: 100%;
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            margin-bottom: 10px;
            font-size: 16px;
        }
        input[type="text"], input[type="number"] {
            width: 100%;
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            margin-bottom: 10px;
            font-size: 16px;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📱 eBay Automation Control</h1>
        
        <div class="card">
            <h2>🚀 Quick Actions</h2>
            <button class="button success" onclick="runCommand('process_ai')">
                Process Listings with AI
            </button>
            <button class="button success" onclick="runCommand('download_all')">
                Download All Listings
            </button>
            <button class="button warning" onclick="runCommand('test_utils')">
                Test eBay Utils
            </button>
            <button class="button" onclick="runCommand('check_status')">
                Check System Status
            </button>
        </div>

        <div class="card">
            <h2>📈 eBay Ads Reports</h2>
            <button class="button success" onclick="runCommand('ebay_ads_report')">
                Generate Ads Report (14 days)
            </button>
            <button class="button" onclick="runCommand('ebay_ads_report_7days')">
                Generate Ads Report (7 days)
            </button>
            <button class="button" onclick="runCommand('ebay_ads_report_30days')">
                Generate Ads Report (30 days)
            </button>
            <div id="report_status" style="margin-top: 10px;"></div>
        </div>

        <div class="card">
            <h2>⚙️ Advanced Controls</h2>
            <select id="model_select">
                <option value="gpt-4o">GPT-4o (Default)</option>
                <option value="gpt-4o-mini">GPT-4o Mini (Faster)</option>
                <option value="o1-preview">O1 Preview</option>
                <option value="o1-mini">O1 Mini</option>
            </select>
            <input type="text" id="item_id" placeholder="Item ID (optional for refresh)">
            <button class="button" onclick="runAdvancedProcess()">
                Run AI Process with Options
            </button>
        </div>

        <div class="card">
            <h2>📊 System Status</h2>
            <div id="status_display">
                <div class="status stopped">No processes running</div>
            </div>
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-value" id="cpu_stat">-</div>
                    <div class="stat-label">CPU Usage</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="mem_stat">-</div>
                    <div class="stat-label">Memory (GB)</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="proc_stat">0</div>
                    <div class="stat-label">Python Processes</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="cache_stat">-</div>
                    <div class="stat-label">Cache Files</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>📝 Recent Activity</h2>
            <div id="log_display" class="log-output">
                No recent activity
            </div>
        </div>

        <div class="card">
            <h2>🔑 eBay OAuth Management</h2>
            <button class="button success" onclick="window.open('/oauth', '_blank')">
                Setup/Refresh eBay OAuth Token
            </button>
            <button class="button" onclick="checkTokenStatus()">
                Check Token Status
            </button>
            <div id="token_status" style="margin-top: 10px;"></div>
        </div>

        <div class="card">
            <h2>🛑 Process Control</h2>
            <button class="button danger" onclick="runCommand('kill_all')">
                Kill All Python Processes
            </button>
            <button class="button danger" onclick="runCommand('clear_cache')">
                Clear Cache Files
            </button>
        </div>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p style="margin-top: 10px; color: white;">Processing...</p>
        </div>
    </div>

    <script>
        function showLoading() {
            document.getElementById('loading').style.display = 'block';
        }
        
        function hideLoading() {
            document.getElementById('loading').style.display = 'none';
        }

        function runCommand(command) {
            showLoading();
            fetch('/api/run', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: command})
            })
            .then(response => response.json())
            .then(data => {
                hideLoading();
                updateStatus();
                if (data.error) {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => {
                hideLoading();
                alert('Error: ' + error);
            });
        }

        function runAdvancedProcess() {
            const model = document.getElementById('model_select').value;
            const itemId = document.getElementById('item_id').value;
            
            showLoading();
            fetch('/api/run_advanced', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    model: model,
                    item_id: itemId
                })
            })
            .then(response => response.json())
            .then(data => {
                hideLoading();
                updateStatus();
            })
            .catch(error => {
                hideLoading();
                alert('Error: ' + error);
            });
        }

        function updateStatus() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    const statusDiv = document.getElementById('status_display');
                    const logDiv = document.getElementById('log_display');
                    
                    if (data.processes && data.processes.length > 0) {
                        statusDiv.innerHTML = data.processes.map(p => 
                            `<div class="status running">🟢 ${p}</div>`
                        ).join('');
                    } else {
                        statusDiv.innerHTML = '<div class="status stopped">No processes running</div>';
                    }
                    
                    if (data.logs) {
                        logDiv.innerText = data.logs;
                    }
                    
                    // Update stats
                    document.getElementById('cpu_stat').innerText = data.cpu + '%';
                    document.getElementById('mem_stat').innerText = data.memory;
                    document.getElementById('proc_stat').innerText = data.python_processes;
                    document.getElementById('cache_stat').innerText = data.cache_files;
                });
        }
        
        function checkTokenStatus() {
            fetch('/api/token_status')
                .then(response => response.json())
                .then(data => {
                    const statusDiv = document.getElementById('token_status');
                    if (data.valid) {
                        statusDiv.innerHTML = `<div class="status running">✅ Token valid for ${data.hours_remaining.toFixed(1)} hours</div>`;
                    } else if (data.exists) {
                        statusDiv.innerHTML = `<div class="status stopped">❌ Token expired - click Setup to refresh</div>`;
                    } else {
                        statusDiv.innerHTML = `<div class="status stopped">⚠️ No token found - click Setup to authenticate</div>`;
                    }
                })
                .catch(error => {
                    document.getElementById('token_status').innerHTML = `<div class="status stopped">Error checking token</div>`;
                });
        }

        // Update status every 5 seconds
        setInterval(updateStatus, 5000);
        
        // Initial status update
        updateStatus();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def get_status():
    try:
        # Get system stats
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_gb = f"{memory.used / (1024**3):.1f}"
        
        # Count Python processes
        python_procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if 'python' in proc.info['name'].lower():
                if proc.info['cmdline']:
                    cmd = ' '.join(proc.info['cmdline'])
                    if any(x in cmd for x in ['aiprocessebay', 'test_ebay', 'ai_download', 'ai_process', 'ebay_ads_report']):
                        python_procs.append(cmd.split('\\')[-1][:50])
        
        # Count cache files
        cache_files = 0
        cache_dirs = ['.cache_llm_data', '.cache_llm_data_desc', '.cache_item_details', '.ebay_api_cache']
        for cache_dir in cache_dirs:
            if os.path.exists(cache_dir):
                cache_files += len(os.listdir(cache_dir))
        
        # Get recent logs
        log_content = ""
        if os.path.exists('ebay_processing.log'):
            with open('ebay_processing.log', 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                log_content = ''.join(lines[-20:])  # Last 20 lines
        
        return jsonify({
            'processes': python_procs,
            'logs': log_content,
            'cpu': cpu_percent,
            'memory': memory_gb,
            'python_processes': len(python_procs),
            'cache_files': cache_files
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/run', methods=['POST'])
def run_command():
    command = request.json.get('command')
    
    commands = {
        'process_ai': 'python aiprocessebay.py',
        'download_all': 'python ai_download_all_listings.py',
        'test_utils': 'python test_ebay_utils.py',
        'check_status': 'tasklist | findstr python',
        'kill_all': 'taskkill /F /IM python.exe',
        'clear_cache': 'rmdir /S /Q .cache_llm_data .cache_llm_data_desc .cache_item_details',
        'ebay_ads_report': 'python ai_ebay_download_automagical.py ebay_ads_report',
        'ebay_ads_report_7days': 'python ai_ebay_download_automagical.py ebay_ads_report_7days',
        'ebay_ads_report_30days': 'python ai_ebay_download_automagical.py ebay_ads_report_30days',
    }
    
    if command not in commands:
        return jsonify({'error': 'Invalid command'})
    
    try:
        if command == 'check_status':
            result = subprocess.run(commands[command], shell=True, capture_output=True, text=True)
            return jsonify({'output': result.stdout, 'status': 'completed'})
        else:
            # Run in background
            proc = subprocess.Popen(commands[command], shell=True, 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   text=True)
            running_processes[command] = proc
            return jsonify({'status': 'started', 'pid': proc.pid})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/run_advanced', methods=['POST'])
def run_advanced():
    model = request.json.get('model', 'gpt-4o')
    item_id = request.json.get('item_id', '')
    
    cmd = f'python aiprocessebay.py --model_name {model}'
    if item_id:
        cmd += f' --refresh {item_id}'
    
    try:
        proc = subprocess.Popen(cmd, shell=True, 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True)
        running_processes['advanced_process'] = proc
        return jsonify({'status': 'started', 'command': cmd})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/logs/<log_type>')
def get_logs(log_type):
    log_files = {
        'processing': 'ebay_processing.log',
        'fixed': 'ebay_processing_fixed.log',
        'stats': 'listing_ai_stats.log'
    }
    
    if log_type not in log_files:
        return jsonify({'error': 'Invalid log type'})
    
    try:
        with open(log_files[log_type], 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            return jsonify({'content': content[-10000:]})  # Last 10KB
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/token_status')
def get_token_status():
    try:
        if not os.path.exists('oauth_tokens.json'):
            return jsonify({'exists': False, 'valid': False})
        
        with open('oauth_tokens.json', 'r') as f:
            token_data = json.load(f)
        
        time_elapsed = time.time() - token_data.get('generated_at', 0)
        hours_remaining = (token_data['expires_in'] - time_elapsed) / 3600
        
        return jsonify({
            'exists': True,
            'valid': hours_remaining > 0,
            'hours_remaining': max(0, hours_remaining),
            'environment': token_data.get('environment', 'unknown')
        })
    except Exception as e:
        return jsonify({'error': str(e), 'exists': False, 'valid': False})

# OAuth integration - run helper in separate thread
def run_oauth_server():
    oauth_helper.setup_routes()
    oauth_helper.app.run(port=5001, debug=False, use_reloader=False)

@app.route('/oauth')
def oauth_redirect():
    # Redirect to OAuth helper server
    return redirect('http://localhost:5001/oauth')

if __name__ == '__main__':
    print("Starting Remote Control Server...")
    print("Access from your phone browser at:")
    print(f"  http://{os.popen('ipconfig').read().split('IPv4 Address')[1].split(':')[1].strip().split()[0]}:5000")
    print("  http://localhost:5000 (from this computer)")
    print("\nMake sure Windows Firewall allows ports 5000 and 5001")
    
    # Start OAuth server in background thread
    oauth_thread = threading.Thread(target=run_oauth_server, daemon=True)
    oauth_thread.start()
    print("OAuth helper server started on port 5001")
    
    app.run(host='0.0.0.0', port=5000, debug=False)