"""
eBay OAuth Token Helper
Automates the OAuth token generation process for eBay API
"""

import webbrowser
import urllib.parse
import requests
import base64
import json
import time
from flask import Flask, request, redirect, render_template_string
import threading
import os

# OAuth endpoints
SANDBOX_AUTH_URL = "https://auth.sandbox.ebay.com/oauth2/authorize"
PRODUCTION_AUTH_URL = "https://auth.ebay.com/oauth2/authorize"
SANDBOX_TOKEN_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
PRODUCTION_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"

# HTML template for OAuth flow
OAUTH_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>eBay OAuth Setup</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .status {
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .success {
            background: #d4edda;
            color: #155724;
        }
        .error {
            background: #f8d7da;
            color: #721c24;
        }
        .info {
            background: #d1ecf1;
            color: #0c5460;
        }
        .button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 25px;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
            width: 100%;
            margin: 10px 0;
        }
        input, select {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
        }
        .token-display {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            font-family: monospace;
            word-break: break-all;
            margin: 10px 0;
        }
        .step {
            background: #f1f3f4;
            padding: 15px;
            border-left: 4px solid #667eea;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔐 eBay OAuth Token Setup</h1>
        
        {% if not started %}
        <form method="POST" action="/oauth/start">
            <h2>Step 1: Enter eBay App Credentials</h2>
            <div class="step">
                <p>Enter your eBay application credentials from the eBay Developer Portal</p>
            </div>
            
            <select name="environment" required>
                <option value="production">Production</option>
                <option value="sandbox">Sandbox</option>
            </select>
            
            <input type="text" name="client_id" placeholder="Client ID (App ID)" required>
            <input type="password" name="client_secret" placeholder="Client Secret (Cert ID)" required>
            <input type="text" name="redirect_uri" value="http://localhost:5001/oauth/callback" readonly>
            
            <h3>Select Scopes (Permissions)</h3>
            <div class="step">
                <label><input type="checkbox" name="scopes" value="https://api.ebay.com/oauth/api_scope/sell.inventory" checked> Sell Inventory</label><br>
                <label><input type="checkbox" name="scopes" value="https://api.ebay.com/oauth/api_scope/sell.marketing" checked> Sell Marketing</label><br>
                <label><input type="checkbox" name="scopes" value="https://api.ebay.com/oauth/api_scope/sell.account"> Sell Account</label><br>
                <label><input type="checkbox" name="scopes" value="https://api.ebay.com/oauth/api_scope/sell.fulfillment"> Sell Fulfillment</label><br>
                <label><input type="checkbox" name="scopes" value="https://api.ebay.com/oauth/api_scope"> View Public Data</label><br>
            </div>
            
            <button type="submit" class="button">Start OAuth Flow</button>
        </form>
        
        {% elif waiting %}
        <div class="status info">
            <h2>Step 2: Authorize with eBay</h2>
            <p>A new browser tab should have opened to eBay's authorization page.</p>
            <p>Please log in to eBay and authorize the application.</p>
            <p>After authorization, you'll be redirected back here automatically.</p>
        </div>
        
        {% elif success %}
        <div class="status success">
            <h2>✅ Success! Token Generated</h2>
            <p>Your OAuth token has been successfully generated and saved.</p>
        </div>
        
        <div class="token-display">
            <strong>Access Token:</strong><br>
            {{ token[:50] }}...
        </div>
        
        <div class="token-display">
            <strong>Refresh Token:</strong><br>
            {{ refresh_token[:50] }}...
        </div>
        
        <div class="status info">
            <p><strong>Token saved to:</strong> oauth_tokens.json</p>
            <p><strong>Expires in:</strong> {{ expires_in }} seconds</p>
            <p>The refresh token can be used to get new access tokens without re-authentication.</p>
        </div>
        
        <button class="button" onclick="window.location.href='/'">Back to Control Panel</button>
        
        {% elif error %}
        <div class="status error">
            <h2>❌ Error</h2>
            <p>{{ error_message }}</p>
        </div>
        <button class="button" onclick="window.location.href='/oauth'">Try Again</button>
        {% endif %}
        
        <hr style="margin: 30px 0; border: 1px solid #e0e0e0;">
        
        <h3>📘 Instructions for Mobile Use</h3>
        <div class="step">
            <ol>
                <li>Open this page on your phone browser</li>
                <li>Enter your eBay app credentials</li>
                <li>Click "Start OAuth Flow"</li>
                <li>You'll be redirected to eBay login</li>
                <li>After authorization, tokens will be saved automatically</li>
            </ol>
        </div>
    </div>
</body>
</html>
'''

class eBayOAuthHelper:
    def __init__(self):
        self.app = Flask(__name__)
        self.oauth_result = None
        self.waiting_for_callback = False
        self.credentials = {}
        
    def setup_routes(self):
        @self.app.route('/oauth')
        def oauth_page():
            return render_template_string(OAUTH_HTML, started=False)
        
        @self.app.route('/oauth/start', methods=['POST'])
        def start_oauth():
            # Store credentials
            self.credentials = {
                'environment': request.form.get('environment'),
                'client_id': request.form.get('client_id'),
                'client_secret': request.form.get('client_secret'),
                'redirect_uri': request.form.get('redirect_uri'),
                'scopes': request.form.getlist('scopes')
            }
            
            # Build authorization URL
            if self.credentials['environment'] == 'production':
                auth_url = PRODUCTION_AUTH_URL
            else:
                auth_url = SANDBOX_AUTH_URL
            
            params = {
                'client_id': self.credentials['client_id'],
                'response_type': 'code',
                'redirect_uri': self.credentials['redirect_uri'],
                'scope': ' '.join(self.credentials['scopes'])
            }
            
            full_url = f"{auth_url}?{urllib.parse.urlencode(params)}"
            
            # Open browser for authorization
            webbrowser.open(full_url)
            self.waiting_for_callback = True
            
            return render_template_string(OAUTH_HTML, waiting=True, started=True)
        
        @self.app.route('/oauth/callback')
        def oauth_callback():
            # Get authorization code from callback
            auth_code = request.args.get('code')
            error = request.args.get('error')
            
            if error:
                return render_template_string(OAUTH_HTML, 
                                             error=True, 
                                             started=True,
                                             error_message=f"Authorization failed: {error}")
            
            if not auth_code:
                return render_template_string(OAUTH_HTML, 
                                             error=True,
                                             started=True, 
                                             error_message="No authorization code received")
            
            # Exchange code for token
            try:
                token_data = self.exchange_code_for_token(auth_code)
                
                # Save tokens to file
                with open('oauth_tokens.json', 'w') as f:
                    json.dump({
                        'access_token': token_data['access_token'],
                        'refresh_token': token_data.get('refresh_token', ''),
                        'expires_in': token_data['expires_in'],
                        'token_type': token_data['token_type'],
                        'environment': self.credentials['environment'],
                        'generated_at': time.time()
                    }, f, indent=2)
                
                # Also update credentials.txt if it exists
                if os.path.exists('credentials.txt'):
                    self.update_credentials_file(token_data['access_token'])
                
                return render_template_string(OAUTH_HTML,
                                             success=True,
                                             started=True,
                                             token=token_data['access_token'],
                                             refresh_token=token_data.get('refresh_token', 'N/A'),
                                             expires_in=token_data['expires_in'])
                
            except Exception as e:
                return render_template_string(OAUTH_HTML,
                                             error=True,
                                             started=True,
                                             error_message=str(e))
    
    def exchange_code_for_token(self, auth_code):
        """Exchange authorization code for access token"""
        if self.credentials['environment'] == 'production':
            token_url = PRODUCTION_TOKEN_URL
        else:
            token_url = SANDBOX_TOKEN_URL
        
        # Prepare credentials
        auth_string = f"{self.credentials['client_id']}:{self.credentials['client_secret']}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {auth_b64}'
        }
        
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': self.credentials['redirect_uri']
        }
        
        response = requests.post(token_url, headers=headers, data=data)
        
        if response.status_code != 200:
            raise Exception(f"Token exchange failed: {response.text}")
        
        return response.json()
    
    def update_credentials_file(self, new_token):
        """Update the credentials.txt file with new token"""
        try:
            with open('credentials.txt', 'r') as f:
                lines = f.readlines()
            
            # Update token line
            for i, line in enumerate(lines):
                if line.startswith('token='):
                    lines[i] = f'token={new_token}\n'
                    break
            else:
                # Add token if not found
                lines.append(f'token={new_token}\n')
            
            with open('credentials.txt', 'w') as f:
                f.writelines(lines)
        except Exception as e:
            print(f"Could not update credentials.txt: {e}")
    
    def refresh_access_token(self, refresh_token):
        """Use refresh token to get new access token"""
        if self.credentials['environment'] == 'production':
            token_url = PRODUCTION_TOKEN_URL
        else:
            token_url = SANDBOX_TOKEN_URL
        
        auth_string = f"{self.credentials['client_id']}:{self.credentials['client_secret']}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {auth_b64}'
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        
        response = requests.post(token_url, headers=headers, data=data)
        
        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.text}")
        
        return response.json()
    
    def run(self, port=5001):
        self.setup_routes()
        print(f"OAuth helper server running on http://localhost:{port}")
        print(f"Navigate to http://localhost:{port}/oauth to start the OAuth flow")
        self.app.run(port=port, debug=False)

def auto_refresh_token():
    """Automatically refresh token when needed"""
    if not os.path.exists('oauth_tokens.json'):
        print("No OAuth tokens found. Run OAuth flow first.")
        return False
    
    with open('oauth_tokens.json', 'r') as f:
        token_data = json.load(f)
    
    # Check if token is expired or about to expire (within 1 hour)
    time_elapsed = time.time() - token_data.get('generated_at', 0)
    if time_elapsed > (token_data['expires_in'] - 3600):
        print("Token expired or expiring soon. Refreshing...")
        
        helper = eBayOAuthHelper()
        # Load credentials if available
        if os.path.exists('credentials.txt'):
            with open('credentials.txt', 'r') as f:
                lines = f.readlines()
                for line in lines:
                    if line.startswith('appid='):
                        helper.credentials['client_id'] = line.split('=')[1].strip()
                    elif line.startswith('certid='):
                        helper.credentials['client_secret'] = line.split('=')[1].strip()
        
        helper.credentials['environment'] = token_data.get('environment', 'production')
        
        try:
            new_token_data = helper.refresh_access_token(token_data['refresh_token'])
            
            # Save new tokens
            with open('oauth_tokens.json', 'w') as f:
                json.dump({
                    'access_token': new_token_data['access_token'],
                    'refresh_token': token_data['refresh_token'],  # Keep original refresh token
                    'expires_in': new_token_data['expires_in'],
                    'token_type': new_token_data['token_type'],
                    'environment': token_data['environment'],
                    'generated_at': time.time()
                }, f, indent=2)
            
            helper.update_credentials_file(new_token_data['access_token'])
            print("Token refreshed successfully!")
            return True
            
        except Exception as e:
            print(f"Failed to refresh token: {e}")
            return False
    else:
        print(f"Token still valid for {(token_data['expires_in'] - time_elapsed) / 3600:.1f} hours")
        return True

if __name__ == "__main__":
    helper = eBayOAuthHelper()
    helper.run()