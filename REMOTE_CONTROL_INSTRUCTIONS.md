# Remote Control Instructions

## How to Control from Your Phone using Claude App

### 1. Start the Server
Run the batch file on your PC:
```
start_remote_control.bat
```

### 2. Note the IP Address
The batch file will show your PC's IP address, something like:
```
Server will be accessible at:
  From your phone: http://192.168.1.100:5000
```

### 3. Access from Claude App on Phone
1. Make sure your phone and PC are on the same WiFi network
2. Open the Claude app on your phone
3. Send a message to Claude with the URL from step 2
4. Claude will open the control panel in the app's browser

### 4. Available Features

#### From Main Control Panel (http://your-ip:5000)
- **Quick Actions**: Run AI processing, download listings, test utilities
- **Advanced Controls**: Choose AI model, specify item IDs
- **System Status**: Monitor CPU, memory, running processes
- **OAuth Management**: Setup/refresh eBay tokens
- **Process Control**: Kill processes, clear cache

#### OAuth Token Setup (http://your-ip:5000/oauth)
- Click "Setup/Refresh eBay OAuth Token"
- Enter your eBay app credentials:
  - Client ID (App ID from eBay Developer Portal)
  - Client Secret (Cert ID from eBay Developer Portal)
- Select environment (Production or Sandbox)
- Choose required scopes/permissions
- You'll be redirected to eBay login
- After authorization, token is saved automatically

### 5. Automated Token Refresh
The system will automatically refresh your OAuth token when:
- Token is expired
- Token will expire within 1 hour
- Any eBay API call is made

### 6. Security Notes
- Windows Firewall must allow Python through on ports 5000 and 5001
- Only devices on your local network can access the server
- OAuth tokens are stored locally in `oauth_tokens.json`
- Credentials are never sent outside your network

### 7. Troubleshooting

#### Can't access from phone?
1. Check both devices are on same WiFi
2. Check Windows Firewall settings
3. Try disabling Windows Firewall temporarily to test
4. Make sure you're using the correct IP address

#### OAuth not working?
1. Check your eBay app credentials are correct
2. Make sure redirect URI is set to `http://localhost:5001/oauth/callback` in eBay app settings
3. For production, you need a production eBay developer account

#### Server won't start?
1. Check if port 5000/5001 is already in use
2. Kill any existing Python processes
3. Run as administrator if needed

### 8. Mobile Browser Direct Access
If Claude app has issues, you can also:
1. Open Chrome/Safari on your phone
2. Type the URL directly: `http://192.168.x.x:5000`
3. Bookmark for easy access