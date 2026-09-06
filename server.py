#!/usr/bin/env python3
"""
Linux Hotspot Manager Captive Portal HTTP Server.
Provides responsive, modern mobile & desktop authentication landing page.
Supports:
1. Username / Password Login
2. Prepaid Voucher Code Redemption
3. Terms of Use / Free Guest Acceptance
Automatic client MAC resolution via /proc/net/arp.
"""
import asyncio, html, json, os, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs
from dbus_next import BusType
from dbus_next.aio import MessageBus

SERVICE = "com.shazid.LinuxHotspotManager"
PATH = "/com/shazid/LinuxHotspotManager"
HOST = os.environ.get("LHM_PORTAL_HOST", "0.0.0.0")
PORT = int(os.environ.get("LHM_PORTAL_PORT", "8080"))

def dbus_call(method, *args):
    async def run():
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        intro = await bus.introspect(SERVICE, PATH)
        obj = bus.get_proxy_object(SERVICE, PATH, intro)
        iface = obj.get_interface(SERVICE)
        py = re.sub(r"(?<!^)(?=[A-Z])", "_", method).lower()
        result = await getattr(iface, "call_" + py)(*args)
        bus.disconnect()
        return result
    return asyncio.run(run())

def get_mac_from_ip(client_ip):
    """Resolve client MAC from kernel ARP table."""
    try:
        with open("/proc/net/arp") as f:
            for line in f:
                p = line.split()
                if len(p) >= 4 and p[0] == client_ip:
                    mac = p[3].lower()
                    if mac != "00:00:00:00:00:00":
                        return mac
    except Exception:
        pass
    return "00:00:00:00:00:00"

def get_portal_html(title, message, terms, error_msg="", success_msg=""):
    title_esc = html.escape(title or "Wi-Fi Hotspot")
    msg_esc = html.escape(message or "Welcome! Please sign in or accept terms to access the Internet.")
    terms_esc = html.escape(terms or "By clicking Continue, you agree to the Terms of Service and Acceptable Use Policy.")
    
    alert_html = ""
    if error_msg:
        alert_html = f'<div class="alert error">{html.escape(error_msg)}</div>'
    elif success_msg:
        alert_html = f'<div class="alert success">{html.escape(success_msg)}</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title_esc}</title>
<style>
  :root {{
    --bg-gradient: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
    --card-bg: rgba(30, 41, 59, 0.75);
    --card-border: rgba(255, 255, 255, 0.1);
    --primary: #3b82f6;
    --primary-hover: #2563eb;
    --accent: #8b5cf6;
    --text: #f8fafc;
    --text-dim: #94a3b8;
    --error: #ef4444;
    --success: #10b981;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: var(--bg-gradient);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text);
    padding: 16px;
  }}
  .card {{
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border-radius: 18px;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    max-width: 440px;
    width: 100%;
    padding: 32px 28px;
  }}
  .header {{
    text-align: center;
    margin-bottom: 24px;
  }}
  .icon-wrap {{
    width: 64px;
    height: 64px;
    margin: 0 auto 16px;
    background: linear-gradient(135deg, var(--primary), var(--accent));
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 8px 20px rgba(59, 130, 246, 0.35);
  }}
  .icon-wrap svg {{
    width: 34px;
    height: 34px;
    fill: #ffffff;
  }}
  h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 8px; }}
  p.desc {{ font-size: 14px; color: var(--text-dim); line-height: 1.5; }}
  .alert {{
    padding: 12px 16px;
    border-radius: 10px;
    font-size: 13px;
    margin-bottom: 18px;
    line-height: 1.4;
  }}
  .alert.error {{ background: rgba(239, 68, 68, 0.2); border: 1px solid var(--error); color: #fca5a5; }}
  .alert.success {{ background: rgba(16, 185, 129, 0.2); border: 1px solid var(--success); color: #6ee7b7; }}
  .tabs {{
    display: flex;
    background: rgba(15, 23, 42, 0.6);
    border-radius: 10px;
    padding: 4px;
    margin-bottom: 20px;
  }}
  .tab-btn {{
    flex: 1;
    border: none;
    background: transparent;
    color: var(--text-dim);
    padding: 8px 0;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
  }}
  .tab-btn.active {{
    background: var(--primary);
    color: #ffffff;
  }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}
  .input-group {{
    margin-bottom: 16px;
    text-align: left;
  }}
  label {{
    display: block;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-dim);
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  input[type="text"], input[type="password"] {{
    width: 100%;
    padding: 12px 14px;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    background: rgba(15, 23, 42, 0.5);
    color: #ffffff;
    font-size: 15px;
    outline: none;
    transition: border 0.2s;
  }}
  input[type="text"]:focus, input[type="password"]:focus {{
    border-color: var(--primary);
  }}
  .terms-box {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin: 16px 0 20px;
    font-size: 13px;
    color: var(--text-dim);
    text-align: left;
    line-height: 1.4;
  }}
  .terms-box input {{ margin-top: 3px; }}
  .btn {{
    width: 100%;
    padding: 14px;
    border-radius: 10px;
    border: none;
    background: linear-gradient(135deg, var(--primary), var(--primary-hover));
    color: #ffffff;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
    transition: transform 0.1s, box-shadow 0.2s;
  }}
  .btn:hover {{ transform: translateY(-1px); box-shadow: 0 6px 20px rgba(59, 130, 246, 0.5); }}
  .btn:active {{ transform: translateY(0); }}
  .footer {{
    margin-top: 24px;
    text-align: center;
    font-size: 11px;
    color: #64748b;
  }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <div class="icon-wrap">
      <svg viewBox="0 0 24 24"><path d="M12 4C7.31 4 3.07 5.9 0 8.98L12 21 24 8.98C20.93 5.9 16.69 4 12 4M2.92 9.07C5.51 6.82 8.62 5.5 12 5.5S18.49 6.82 21.08 9.07L12 18.15 2.92 9.07Z"/></svg>
    </div>
    <h1>{title_esc}</h1>
    <p class="desc">{msg_esc}</p>
  </div>

  {alert_html}

  <div class="tabs">
    <button type="button" class="tab-btn active" onclick="switchTab('user')">User Login</button>
    <button type="button" class="tab-btn" onclick="switchTab('voucher')">Voucher</button>
    <button type="button" class="tab-btn" onclick="switchTab('free')">Free Guest</button>
  </div>

  <!-- User Login Tab -->
  <form method="post" id="tab-user" class="tab-content active">
    <input type="hidden" name="login_type" value="user">
    <div class="input-group">
      <label>Username</label>
      <input type="text" name="username" placeholder="Enter username" autocomplete="username">
    </div>
    <div class="input-group">
      <label>Password</label>
      <input type="password" name="password" placeholder="••••••••" autocomplete="current-password">
    </div>
    <button type="submit" class="btn">Connect to Internet</button>
  </form>

  <!-- Voucher Tab -->
  <form method="post" id="tab-voucher" class="tab-content">
    <input type="hidden" name="login_type" value="voucher">
    <div class="input-group">
      <label>Prepaid Voucher Code</label>
      <input type="text" name="voucher_code" placeholder="e.g. ABCD1234EFGH" style="letter-spacing:2px; text-transform:uppercase;">
    </div>
    <button type="submit" class="btn">Redeem Voucher</button>
  </form>

  <!-- Free Guest Tab -->
  <form method="post" id="tab-free" class="tab-content">
    <input type="hidden" name="login_type" value="free">
    <div class="terms-box">
      <input type="checkbox" name="terms" id="free-terms" required>
      <label for="free-terms" style="text-transform:none; font-weight:normal; margin:0; cursor:pointer;">
        {terms_esc}
      </label>
    </div>
    <button type="submit" class="btn">Accept &amp; Connect</button>
  </form>

  <div class="footer">
    Protected by Linux Hotspot Manager
  </div>
</div>

<script>
function switchTab(name) {{
  document.querySelectorAll('.tab-btn').forEach((b, i) => {{
    b.classList.remove('active');
  }});
  document.querySelectorAll('.tab-content').forEach(c => {{
    c.classList.remove('active');
  }});
  if (name === 'user') {{
    document.querySelectorAll('.tab-btn')[0].classList.add('active');
    document.getElementById('tab-user').classList.add('active');
  }} else if (name === 'voucher') {{
    document.querySelectorAll('.tab-btn')[1].classList.add('active');
    document.getElementById('tab-voucher').classList.add('active');
  }} else {{
    document.querySelectorAll('.tab-btn')[2].classList.add('active');
    document.getElementById('tab-free').classList.add('active');
  }}
}}
</script>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    server_version = "LHMPortal/4.1.0"

    def log_message(self, fmt, *args):
        return

    def config(self):
        try:
            return json.loads(dbus_call("GetPortalConfig"))
        except Exception:
            return {}

    def do_GET(self):
        c = self.config()
        title = c.get("title", "Linux Hotspot Manager")
        msg = c.get("message", "Welcome! Sign in or accept the terms to continue.")
        terms = c.get("terms", "By continuing you accept the Terms of Service.")

        body = get_portal_html(title, msg, terms)
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        length = min(int(self.headers.get("Content-Length", "0")), 16384)
        raw_body = self.rfile.read(length).decode("utf-8", "ignore")
        form = parse_qs(raw_body)

        client_ip = self.client_address[0]
        mac = get_mac_from_ip(client_ip)
        iface = os.environ.get("LHM_HOTSPOT_IFACE", "wlan0")

        login_type = form.get("login_type", [""])[0]
        user = form.get("username", [""])[0]
        password = form.get("password", [""])[0]
        voucher = form.get("voucher_code", [""])[0]
        terms_accepted = form.get("terms", [""])[0]

        cfg = self.config()
        title = cfg.get("title", "Linux Hotspot Manager")
        msg = cfg.get("message", "Welcome! Sign in or accept the terms to continue.")
        terms = cfg.get("terms", "By continuing you accept the Terms of Service.")
        redirect = cfg.get("redirect", "")

        try:
            if login_type == "voucher" or voucher:
                code = voucher or user
                result = dbus_call("AuthenticatePortalClient", iface, mac, code, "", 3600)
            elif user and password:
                result = dbus_call("AuthenticatePortalClient", iface, mac, user, password, 3600)
            elif terms_accepted or login_type == "free":
                result = dbus_call("AcceptPortalTerms", iface, mac, 3600)
            else:
                raise ValueError("Credentials or terms acceptance required")

            token = json.loads(result).get("token", "")
            if redirect:
                body = f"""<!DOCTYPE html><html><head><meta http-equiv="refresh" content="1;url={html.escape(redirect, quote=True)}"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Authenticated</title></head><body style="background:#0f172a;color:#f8fafc;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center;"><div><h2>✓ Access Granted</h2><p style="color:#94a3b8;margin-top:8px;">Redirecting you to the Internet...</p></div></body></html>"""
            else:
                body = f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Authenticated</title></head><body style="background:#0f172a;color:#f8fafc;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center;"><div><h2 style="color:#10b981;">✓ Connected!</h2><p style="color:#94a3b8;margin:12px 0;">You are now connected to the Internet.</p><p style="font-size:12px;color:#64748b;">Session: {html.escape(token[:12])}...</p></div></body></html>"""
            code = 200
        except Exception as e:
            body = get_portal_html(title, msg, terms, error_msg=str(e))
            code = 403

        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
