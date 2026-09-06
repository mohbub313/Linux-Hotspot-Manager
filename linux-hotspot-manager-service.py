#!/usr/bin/env python3
"""
Linux Hotspot Manager privileged host service.

Design goals:
- No shell=True for privileged operations.
- Persistent SQLite state.
- NetworkManager owns AP configuration.
- nftables owns filtering/accounting.
- tc owns optional per-client shaping.
- dnsmasq is scoped to the configured hotspot interface.
"""
import asyncio
import hashlib
import ipaddress
import json
import os
import re
import secrets
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path
from dbus_next import Variant, BusType
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method

# Ensure system administrative binaries (/sbin, /usr/sbin) are reachable
os.environ["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:" + os.environ.get("PATH", "")

SERVICE = "com.shazid.LinuxHotspotManager"
PATH = "/com/shazid/LinuxHotspotManager"
IFACE = SERVICE
DATA = Path("/var/lib/linux-hotspot-manager")
DB_PATH = DATA / "manager.sqlite3"
NFT_TABLE = "linux_hotspot_manager"
NFT_FAMILY = "inet"

MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")
IFACE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,32}$")
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

def valid_mac(v):
    return bool(v and MAC_RE.fullmatch(v))

def valid_iface(v):
    return bool(v and IFACE_RE.fullmatch(v))

def valid_ipv4(v):
    try:
        ipaddress.IPv4Address(v)
        return True
    except ValueError:
        return False

def valid_domain(v):
    return bool(v and DOMAIN_RE.fullmatch(v.lower().rstrip(".")))

# Test aliases
_valid_mac = valid_mac
_valid_iface = valid_iface
_valid_ipv4 = valid_ipv4
_valid_domain = valid_domain

def run(argv, timeout=20):
    return subprocess.run(argv, text=True, capture_output=True, timeout=timeout, check=False)

def must_run(argv, timeout=20):
    r = run(argv, timeout)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or f"command failed: {argv[0]}")
    return r.stdout.strip()

def atomic_write_json(file_path: Path, data: dict):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = file_path.parent
    with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False) as tf:
        json.dump(data, tf)
        temp_name = tf.name
    os.replace(temp_name, file_path)

def get_default_wan_interface():
    """Find the default outbound network interface dynamically from the routing table."""
    r = run(["ip", "-4", "route", "show", "default"])
    if r.returncode == 0 and r.stdout.strip():
        parts = r.stdout.splitlines()[0].split()
        if "dev" in parts:
            idx = parts.index("dev")
            if idx + 1 < len(parts):
                return parts[idx + 1]
    return None

def get_wifi_station_info():
    """Check if any Wi-Fi interface is currently connected as a station to an upstream network."""
    r = run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"])
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            p = line.split(":")
            if len(p) >= 4 and p[1] == "wifi" and "connected" in p[2].lower() and p[3] != "":
                if not p[3].lower().startswith("hotspot") and not p[3].lower().startswith("linuxhotspot"):
                    return p[0], p[3]
    return None, None

def get_station_channel(iface="wlo1"):
    """Get current operating channel and band of the connected station interface."""
    r = run(["iw", "dev", iface, "info"])
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("channel "):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                ch = int(parts[1])
                band = "a" if ch > 14 else "bg"
                return ch, band
    return 0, "auto"

def ensure_ap_interface(parent_iface="wlo1"):
    """
    Ensure virtual AP interface (ap0) exists on the same wiphy so that station Wi-Fi
    does NOT disconnect when the hotspot is activated.
    """
    r = run(["ip", "link", "show", "ap0"])
    if r.returncode == 0:
        return "ap0"

    r_mac = run(["cat", f"/sys/class/net/{parent_iface}/address"])
    parent_mac = r_mac.stdout.strip()
    if valid_mac(parent_mac):
        octets = [int(x, 16) for x in parent_mac.split(":")]
        octets[0] = (octets[0] | 0x02) & 0xFE
        octets[-1] = (octets[-1] + 1) % 256
        ap_mac = ":".join(f"{x:02x}" for x in octets)
    else:
        ap_mac = "02:00:00:11:22:33"

    r_add = run(["iw", "dev", parent_iface, "interface", "add", "ap0", "type", "__ap", "addr", ap_mac])
    if r_add.returncode != 0:
        r_add = run(["iw", "phy", "phy0", "interface", "add", "ap0", "type", "__ap"])

    if r_add.returncode == 0:
        run(["ip", "link", "set", "dev", "ap0", "up"])
        return "ap0"

    return parent_iface

def cleanup_ap_interface():
    """Remove virtual ap0 interface if it exists."""
    r = run(["ip", "link", "show", "ap0"])
    if r.returncode == 0:
        run(["iw", "dev", "ap0", "del"])

def hash_password(password):
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${key.hex()}"

def _nft_json():
    r = run(["nft", "-j", "list", "table", NFT_FAMILY, NFT_TABLE])
    if r.returncode == 0 and r.stdout.strip():
        try:
            return json.loads(r.stdout)
        except Exception:
            pass
    return {"nftables": []}

def _parse_client_counters(iface):
    nft_data = _nft_json()
    clients = {}
    for item in nft_data.get("nftables", []):
        rule = item.get("rule")
        if not rule:
            continue
        comment = rule.get("comment", "")
        if not comment.startswith("lhm:"):
            continue
        c_parts = comment[4:].rsplit(":", 1)
        if len(c_parts) != 2:
            continue
        mac = c_parts[0].lower()
        direction = c_parts[1]

        exprs = rule.get("expr", [])
        packets = 0
        byte_count = 0
        matched_iface = True
        for expr in exprs:
            if "match" in expr:
                m = expr["match"]
                left = m.get("left")
                right = m.get("right")
                if left in ("iifname", "oifname"):
                    if iface and right != iface:
                        matched_iface = False
                        break
            if "counter" in expr:
                cnt = expr["counter"]
                packets = cnt.get("packets", 0)
                byte_count = cnt.get("bytes", 0)

        if not matched_iface:
            continue

        if mac not in clients:
            clients[mac] = {
                "mac": mac,
                "rx_bytes": 0,
                "tx_bytes": 0,
                "packets_rx": 0,
                "packets_tx": 0,
            }

        if direction == "upload":
            clients[mac]["tx_bytes"] += byte_count
            clients[mac]["packets_tx"] += packets
        elif direction == "download":
            clients[mac]["rx_bytes"] += byte_count
            clients[mac]["packets_rx"] += packets

    return list(clients.values())

def _dns_block_file():
    return DATA / "dnsmasq-blocked.conf"

def _dns_allow_file():
    return DATA / "dnsmasq-allowed.conf"

def _write_domain_lists(blocked_list, allowed_list):
    b_out = []
    for d in blocked_list:
        clean = d.lower().lstrip("*.").strip(".")
        if _valid_domain(clean) and clean not in b_out:
            b_out.append(clean)
    a_out = []
    for d in allowed_list:
        clean = d.lower().lstrip("*.").strip(".")
        if _valid_domain(clean) and clean not in a_out:
            a_out.append(clean)

    try:
        b_path = Path(_dns_block_file())
        b_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=b_path.parent, delete=False) as tf:
            for domain in b_out:
                tf.write(f"address=/{domain}/\n")
            temp_name = tf.name
        os.replace(temp_name, b_path)
    except Exception:
        pass

    try:
        a_path = Path(_dns_allow_file())
        a_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=a_path.parent, delete=False) as tf:
            for domain in a_out:
                tf.write(f"server=/{domain}/#\n")
            temp_name = tf.name
        os.replace(temp_name, a_path)
    except Exception:
        pass

    return b_out, a_out

def _portal_session_path():
    return DATA / "portal_sessions.json"

def _save_portal_sessions(sessions):
    atomic_write_json(Path(_portal_session_path()), sessions)

def _load_portal_sessions():
    p = Path(_portal_session_path())
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

def _portal_session_valid(mac, token):
    sessions = _load_portal_sessions()
    sess = sessions.get(mac.lower()) or sessions.get(mac)
    if not sess:
        return False
    if sess.get("token") != token:
        return False
    if not sess.get("authenticated", False):
        return False
    expires_at = sess.get("expires_at", 0)
    if expires_at and expires_at < time.time():
        return False
    return True

async def _nm_devices():
    proc = await asyncio.create_subprocess_exec(
        "nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    devices = []
    if proc.returncode == 0:
        for line in stdout.decode("utf-8", errors="ignore").splitlines():
            p = line.split(":")
            if len(p) >= 3 and valid_iface(p[0]):
                devices.append({
                    "device": p[0],
                    "type": p[1],
                    "state": p[2],
                    "connection": p[3] if len(p) > 3 else ""
                })
    return devices

async def _nm_add_ap(interface, ssid, password, band="auto", channel=0):
    if not ssid or len(ssid) > 32 or len(password) < 8 or len(password) > 63:
        raise ValueError("Invalid SSID or password")
    con_name = f"Hotspot-{ssid}"
    iface_arg = interface if (interface and interface != "*" and valid_iface(interface)) else "*"

    chk = await asyncio.create_subprocess_exec(
        "nmcli", "-t", "-f", "NAME", "connection", "show", con_name,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await chk.communicate()

    if chk.returncode != 0:
        cmd = [
            "nmcli", "connection", "add", "type", "wifi",
            "ifname", iface_arg,
            "con-name", con_name,
            "autoconnect", "no",
            "802-11-wireless.mode", "ap",
            "802-11-wireless.ssid", ssid,
            "ipv4.method", "shared",
            "ipv6.method", "disabled"
        ]
        if band in ("a", "bg"):
            cmd.extend(["802-11-wireless.band", band])
        if channel and channel > 0:
            cmd.extend(["802-11-wireless.channel", str(channel)])
        p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await p.communicate()

    mod_cmd = ["nmcli", "connection", "modify", con_name,
               "wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password]
    if band in ("a", "bg"):
        mod_cmd.extend(["802-11-wireless.band", band])
    if channel and channel > 0:
        mod_cmd.extend(["802-11-wireless.channel", str(channel)])
    p2 = await asyncio.create_subprocess_exec(*mod_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await p2.communicate()

    up = await asyncio.create_subprocess_exec(
        "nmcli", "connection", "up", con_name,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    up_out, up_err = await up.communicate()
    if up.returncode != 0:
        raise RuntimeError(up_err.decode().strip() or "Failed to activate hotspot")
    return {"status": "started", "connection": con_name, "ssid": ssid}

async def _nm_deactivate(active_path_or_name):
    name = str(active_path_or_name)
    p = await asyncio.create_subprocess_exec(
        "nmcli", "connection", "down", name,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await p.communicate()
    return True

class Manager(ServiceInterface):
    def __init__(self, db_path=None):
        super().__init__(IFACE)
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = DB_PATH
        try:
            self.db_path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
            self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        except (PermissionError, sqlite3.OperationalError):
            fallback_dir = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "linux-hotspot-manager"
            fallback_dir.mkdir(mode=0o750, parents=True, exist_ok=True)
            self.db_path = fallback_dir / "manager.sqlite3"
            self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS settings(
          key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
          expires_at INTEGER, time_quota INTEGER DEFAULT 0,
          data_quota INTEGER DEFAULT 0, max_sessions INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS sessions(
          id INTEGER PRIMARY KEY, username TEXT, mac TEXT NOT NULL, ip TEXT,
          started_at INTEGER NOT NULL, ended_at INTEGER,
          bytes_up INTEGER NOT NULL DEFAULT 0, bytes_down INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS clients(
          mac TEXT PRIMARY KEY, blocked INTEGER NOT NULL DEFAULT 0,
          down_kbit INTEGER DEFAULT 0, up_kbit INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS firewall_ports(
          proto TEXT NOT NULL CHECK(proto IN ('tcp','udp')),
          port INTEGER NOT NULL CHECK(port BETWEEN 1 AND 65535),
          PRIMARY KEY(proto,port)
        );
        CREATE TABLE IF NOT EXISTS domain_rules(
          domain TEXT PRIMARY KEY, action TEXT NOT NULL CHECK(action IN ('allow','block'))
        );
        CREATE TABLE IF NOT EXISTS profiles(
          name TEXT PRIMARY KEY, ssid TEXT NOT NULL, band TEXT DEFAULT 'auto',
          security TEXT DEFAULT 'wpa2', hidden INTEGER DEFAULT 0,
          hotspot_iface TEXT, upstream_iface TEXT, gateway TEXT DEFAULT '10.42.0.1',
          dhcp_start TEXT DEFAULT '10.42.0.10', dhcp_end TEXT DEFAULT '10.42.0.254',
          dns TEXT DEFAULT '1.1.1.1,8.8.8.8'
        );
        CREATE TABLE IF NOT EXISTS vouchers(
          code TEXT PRIMARY KEY, created_at INTEGER NOT NULL, expires_at INTEGER, duration INTEGER DEFAULT 0,
          data_quota INTEGER DEFAULT 0, down_kbit INTEGER DEFAULT 0, up_kbit INTEGER DEFAULT 0, used INTEGER DEFAULT 0, used_by TEXT
        );
        CREATE TABLE IF NOT EXISTS firewall_rules(
          id INTEGER PRIMARY KEY AUTOINCREMENT, proto TEXT NOT NULL, port INTEGER NOT NULL, action TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS portal_config(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS free_urls(domain TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS mac_rules(mac TEXT PRIMARY KEY, action TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS url_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, mac TEXT, ip TEXT, url TEXT);
        CREATE TABLE IF NOT EXISTS staff(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT, role TEXT DEFAULT 'admin', enabled INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS pricing(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, price REAL DEFAULT 0, duration INTEGER DEFAULT 0, data_quota INTEGER DEFAULT 0, down_kbit INTEGER DEFAULT 0, up_kbit INTEGER DEFAULT 0);
        """)
        self.db.commit()

    def log(self, kind, message):
        self.db.execute("INSERT INTO logs(ts,kind,message) VALUES(?,?,?)", (int(time.time()), kind, message))
        self.db.commit()

    def setting(self, key, default=""):
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        self.db.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        self.db.commit()

    def _int_setting(self, k, d=0):
        try:
            return int(self.setting(k, str(d)))
        except Exception:
            return d

    @method()
    async def ListNetworkManagerDevices(self) -> "s":
        return json.dumps(await _nm_devices())

    @method()
    async def CreateAndActivateWifiAP(self, interface: "s", ssid: "s", password: "s", band: "s", channel: "u") -> "s":
        return json.dumps(await _nm_add_ap(interface, ssid, password, band, int(channel)))

    @method()
    async def DeactivateNetworkManagerConnection(self, active_path: "o") -> "b":
        await _nm_deactivate(active_path)
        return True

    @method()
    def Ping(self) -> "s":
        return "pong"

    @method()
    def GetStatus(self) -> "s":
        return json.dumps({
            "version": "4.1.0",
            "service": "ready",
            "hotspot": self.setting("hotspot_state", "stopped"),
            "interface": self.setting("hotspot_iface", ""),
            "connection": self.setting("hotspot_connection", "")
        })

    @method()
    def StartHotspot(self, connection: "s", password: "s") -> "s":
        if not connection or len(connection) > 64 or len(password) < 8 or len(password) > 63:
            raise ValueError("Invalid hotspot settings")

        ssid = connection
        con_name = connection

        station_iface, station_con = get_wifi_station_info()
        hotspot_iface = "wlo1"
        ch = 0
        band = "bg"

        if station_iface:
            ap_iface = ensure_ap_interface(station_iface)
            if ap_iface != station_iface:
                hotspot_iface = ap_iface
                ch, band = get_station_channel(station_iface)
            else:
                hotspot_iface = station_iface
        else:
            r_dev = run(["nmcli", "-t", "-f", "DEVICE,TYPE", "device"])
            for line in r_dev.stdout.splitlines():
                p = line.split(":")
                if len(p) >= 2 and p[1] == "wifi":
                    hotspot_iface = p[0]
                    break
            ch = 6
            band = "bg"

        run(["nmcli", "connection", "delete", con_name])

        cmd_add = [
            "nmcli", "connection", "add",
            "type", "wifi",
            "ifname", hotspot_iface,
            "con-name", con_name,
            "autoconnect", "no",
            "802-11-wireless.mode", "ap",
            "802-11-wireless.ssid", ssid,
            "802-11-wireless-security.key-mgmt", "wpa-psk",
            "802-11-wireless-security.proto", "rsn",
            "802-11-wireless-security.pairwise", "ccmp",
            "802-11-wireless-security.group", "ccmp",
            "802-11-wireless-security.pmf", "1",
            "802-11-wireless-security.psk", password,
            "ipv4.method", "shared",
            "ipv6.method", "disabled"
        ]

        if band in ("a", "bg"):
            cmd_add.extend(["802-11-wireless.band", band])
        if ch > 0:
            cmd_add.extend(["802-11-wireless.channel", str(ch)])

        must_run(cmd_add)

        r_up = run(["nmcli", "connection", "up", con_name])
        if r_up.returncode != 0:
            run(["nmcli", "connection", "modify", con_name, "802-11-wireless.channel", "0"])
            r_up2 = run(["nmcli", "connection", "up", con_name])
            if r_up2.returncode != 0:
                raise RuntimeError(r_up2.stderr.strip() or r_up.stderr.strip() or "Failed to activate hotspot")

        self.set_setting("hotspot_state", "running")
        self.set_setting("hotspot_connection", con_name)
        self.set_setting("hotspot_iface", hotspot_iface)
        self.log("hotspot", f"started {con_name} on {hotspot_iface}")
        self.apply_nft()
        return "started"

    @method()
    def StopHotspot(self, connection: "s") -> "s":
        if not connection or len(connection) > 64:
            raise ValueError("Invalid connection name")
        r = run(["nmcli", "connection", "down", connection])

        cleanup_ap_interface()

        station_iface, station_con = get_wifi_station_info()
        if not station_con:
            # Dynamically reconnect to wifi station if possible instead of hardcoded wlo1
            r_dev = run(["nmcli", "-t", "-f", "DEVICE,TYPE", "device"])
            target_wifi = "wlo1"
            for line in r_dev.stdout.splitlines():
                p = line.split(":")
                if len(p) >= 2 and p[1] == "wifi":
                    target_wifi = p[0]
                    break
            run(["nmcli", "device", "connect", target_wifi])

        self.set_setting("hotspot_state", "stopped")
        self.log("hotspot", f"stopped {connection}")
        return "stopped" if r.returncode == 0 else "already-stopped"

    @method()
    def SetClientBlocked(self, mac: "s", blocked: "b") -> "s":
        if not valid_mac(mac):
            raise ValueError("Invalid MAC")
        self.db.execute("""INSERT INTO clients(mac,blocked) VALUES(?,?)
          ON CONFLICT(mac) DO UPDATE SET blocked=excluded.blocked""", (mac.lower(), int(blocked)))
        self.db.commit()
        self.apply_nft()
        return "ok"

    @method()
    def SetBandwidthProfile(self, mac: "s", down_kbit: "u", up_kbit: "u") -> "s":
        if not valid_mac(mac) or down_kbit > 10000000 or up_kbit > 10000000:
            raise ValueError("Invalid bandwidth")
        self.db.execute("""INSERT INTO clients(mac,down_kbit,up_kbit) VALUES(?,?,?)
          ON CONFLICT(mac) DO UPDATE SET down_kbit=excluded.down_kbit,up_kbit=excluded.up_kbit""",
          (mac.lower(), down_kbit, up_kbit))
        self.db.commit()
        return "saved"

    @method()
    def AddFirewallPort(self, proto: "s", port: "u") -> "s":
        if proto not in ("tcp", "udp") or not (1 <= port <= 65535):
            raise ValueError("Invalid port")
        self.db.execute("INSERT OR IGNORE INTO firewall_ports(proto,port) VALUES(?,?)", (proto, port))
        self.db.commit()
        self.apply_nft()
        return "saved"

    @method()
    def RemoveFirewallPort(self, proto: "s", port: "u") -> "s":
        self.db.execute("DELETE FROM firewall_ports WHERE proto=? AND port=?", (proto, port))
        self.db.commit()
        self.apply_nft()
        return "removed"

    def apply_nft(self):
        """Rebuild dedicated nftables table atomically with NAT masquerade, accounting, and filtering."""
        run(["sysctl", "-w", "net.ipv4.ip_forward=1"])

        iface = self.setting("hotspot_iface", "")
        wan_iface = get_default_wan_interface()

        hotspot_subnet = "10.42.0.0/16"
        if iface and valid_iface(iface):
            r_ip = run(["ip", "-4", "addr", "show", "dev", iface])
            for line in r_ip.stdout.splitlines():
                line = line.strip()
                if line.startswith("inet "):
                    p = line.split()[1]
                    try:
                        net = ipaddress.ipv4_network(p, strict=False)
                        hotspot_subnet = str(net)
                        break
                    except Exception:
                        pass

        lines = [
            f"table {NFT_FAMILY} {NFT_TABLE} {{",
            "  chain forward {",
            "    type filter hook forward priority 0; policy accept;",
            "    ct state established,related accept",
            f"    ip saddr {hotspot_subnet} accept",
        ]

        blocked = [x[0].lower() for x in self.db.execute("SELECT mac FROM clients WHERE blocked=1")]
        for mac in blocked:
            lines.append(f"    ether saddr {mac} drop")

        ports = self.db.execute("SELECT proto,port FROM firewall_ports ORDER BY proto,port").fetchall()
        for proto, port in ports:
            lines.append(f"    {proto} dport {port} drop")

        rules = self.db.execute("SELECT proto,port,action FROM firewall_rules").fetchall()
        for proto, port, action in rules:
            target = "drop" if action == "block" else "accept"
            lines.append(f"    {proto} dport {port} {target}")

        if self.setting("p2p_blocking") == "1":
            lines.append("    tcp dport { 6881-6889, 51413 } drop")
            lines.append("    udp dport { 6881-6889, 51413 } drop")

        leases = self._get_clients()
        for cl in leases:
            mac = cl["mac"].lower()
            if iface:
                lines.append(f'    iifname "{iface}" ether saddr {mac} counter comment "lhm:{mac}:upload"')
                lines.append(f'    oifname "{iface}" ether daddr {mac} counter comment "lhm:{mac}:download"')
            else:
                lines.append(f'    ether saddr {mac} counter comment "lhm:{mac}:upload"')
                lines.append(f'    ether daddr {mac} counter comment "lhm:{mac}:download"')

        lines.append("  }")

        lines.append("  chain input {")
        lines.append("    type filter hook input priority 0; policy accept;")
        lines.append("    udp dport { 53, 67, 68 } accept")
        lines.append("    tcp dport 53 accept")
        lines.append("  }")

        lines.append("  chain prerouting {")
        lines.append("    type nat hook prerouting priority dstnat; policy accept;")
        for key, val in self.db.execute("SELECT key, value FROM settings WHERE key LIKE 'portforward:%'"):
            parts = key.split(":")
            if len(parts) >= 3:
                proto = parts[1]
                listen = parts[2]
                try:
                    data = json.loads(val)
                    dst_ip = data.get("destination_ip", "")
                    dst_port = str(data.get("destination_port", ""))
                    if valid_ipv4(dst_ip) and dst_port.isdigit():
                        lines.append(f"    {proto} dport {listen} dnat to {dst_ip}:{dst_port}")
                except Exception:
                    pass
        lines.append("  }")

        lines.append("  chain postrouting {")
        lines.append("    type nat hook postrouting priority srcnat; policy accept;")
        if wan_iface:
            lines.append(f'    ip saddr {hotspot_subnet} oifname "{wan_iface}" masquerade')
        else:
            lines.append(f"    ip saddr {hotspot_subnet} masquerade")
        lines.append("  }")

        lines.append("}")

        ruleset = "\n".join(lines) + "\n"

        run(["nft", "delete", "table", NFT_FAMILY, NFT_TABLE])
        nft_run_dir = Path("/run/linux-hotspot-manager")
        try:
            nft_run_dir.mkdir(parents=True, exist_ok=True)
            nft_file = nft_run_dir / "rules.nft"
            nft_file.write_text(ruleset)
            r = run(["nft", "-f", str(nft_file)])
            if r.returncode != 0:
                run(["iptables", "-t", "nat", "-A", "POSTROUTING", "-s", hotspot_subnet, "-j", "MASQUERADE"])
        except Exception:
            run(["iptables", "-t", "nat", "-A", "POSTROUTING", "-s", hotspot_subnet, "-j", "MASQUERADE"])

    @method()
    def AddDomainRule(self, domain: "s", action: "s") -> "s":
        domain = domain.lower().rstrip(".")
        if not valid_domain(domain) or action not in ("allow", "block"):
            raise ValueError("Invalid domain rule")
        self.db.execute("""INSERT INTO domain_rules(domain,action) VALUES(?,?)
          ON CONFLICT(domain) DO UPDATE SET action=excluded.action""", (domain, action))
        self.db.commit()
        blocked = [r[0] for r in self.db.execute("SELECT domain FROM domain_rules WHERE action='block'")]
        allowed = [r[0] for r in self.db.execute("SELECT domain FROM domain_rules WHERE action='allow'")]
        _write_domain_lists(blocked, allowed)
        return "saved"

    @method()
    def ListDomainRules(self) -> "s":
        rows = [{"domain": r[0], "action": r[1]} for r in self.db.execute("SELECT domain, action FROM domain_rules ORDER BY domain")]
        return json.dumps(rows)

    @method()
    def RemoveDomainRule(self, domain: "s") -> "s":
        self.db.execute("DELETE FROM domain_rules WHERE domain=?", (domain.lower().rstrip("."),))
        self.db.commit()
        blocked = [r[0] for r in self.db.execute("SELECT domain FROM domain_rules WHERE action='block'")]
        allowed = [r[0] for r in self.db.execute("SELECT domain FROM domain_rules WHERE action='allow'")]
        _write_domain_lists(blocked, allowed)
        return "deleted"

    def _interface_bytes(self, iface):
        if not valid_iface(iface):
            raise ValueError("Invalid interface")
        rx = Path("/sys/class/net") / iface / "statistics/rx_bytes"
        tx = Path("/sys/class/net") / iface / "statistics/tx_bytes"
        try:
            return int(rx.read_text().strip()), int(tx.read_text().strip())
        except (FileNotFoundError, ValueError):
            return 0, 0

    @method()
    def GetTrafficStats(self, iface: "s") -> "s":
        rx, tx = self._interface_bytes(iface)
        return json.dumps({
            "interface": iface,
            "rx_bytes": rx,
            "tx_bytes": tx,
            "timestamp": int(time.time())
        })

    @method()
    def CreateUser(self, username: "s", password: "s", time_quota: "u", data_quota: "t") -> "s":
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", username):
            raise ValueError("Invalid username")
        if len(password) < 8 or len(password) > 256:
            raise ValueError("Invalid password length")
        self.db.execute("""INSERT INTO users(username,password_hash,time_quota,data_quota)
          VALUES(?,?,?,?)""", (username, hash_password(password), time_quota, data_quota))
        self.db.commit()
        return "created"

    @method()
    def ListUsers(self) -> "s":
        rows = []
        for r in self.db.execute("SELECT id,username,enabled,expires_at,time_quota,data_quota,max_sessions FROM users ORDER BY username"):
            rows.append(dict(zip(["id", "username", "enabled", "expires_at", "time_quota", "data_quota", "max_sessions"], r)))
        return json.dumps(rows)

    @method()
    def GenerateVouchers(self, count: "u", duration: "u", data_quota: "t", down_kbit: "u", up_kbit: "u") -> "s":
        if not 1 <= count <= 10000:
            raise ValueError("Invalid voucher count")
        out = []
        now = int(time.time())
        for _ in range(int(count)):
            code = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12].upper()
            while self.db.execute("SELECT 1 FROM vouchers WHERE code=?", (code,)).fetchone():
                code = secrets.token_hex(6).upper()
            exp = now + int(duration) if duration else None
            self.db.execute("INSERT INTO vouchers(code,created_at,expires_at,duration,data_quota,down_kbit,up_kbit) VALUES(?,?,?,?,?,?,?)",
                            (code, now, exp, duration, data_quota, down_kbit, up_kbit))
            out.append(code)
        self.db.commit()
        self.log("voucher", f"generated {len(out)} vouchers")
        return json.dumps(out)

    @method()
    def ListVouchers(self) -> "s":
        rows = []
        for r in self.db.execute("SELECT code,created_at,expires_at,duration,data_quota,down_kbit,up_kbit,used,used_by FROM vouchers ORDER BY created_at DESC"):
            rows.append(dict(zip(["code", "created_at", "expires_at", "duration", "data_quota", "down_kbit", "up_kbit", "used", "used_by"], r)))
        return json.dumps(rows)

    @method()
    def RedeemVoucher(self, code: "s", mac: "s") -> "s":
        if not code or not valid_mac(mac):
            raise ValueError("Invalid voucher or MAC")
        row = self.db.execute("SELECT expires_at,used FROM vouchers WHERE code=?", (code.upper(),)).fetchone()
        if not row:
            raise ValueError("Voucher not found")
        if row[1] or (row[0] and row[0] < int(time.time())):
            raise ValueError("Voucher expired or already used")
        self.db.execute("UPDATE vouchers SET used=1,used_by=? WHERE code=?", (mac.lower(), code.upper()))
        self.db.commit()
        self.log("voucher", f"redeemed {code.upper()} for {mac.lower()}")
        return "redeemed"

    @method()
    def SetPortalConfig(self, title: "s", message: "s", redirect: "s", terms: "s") -> "s":
        for k, v in (("title", title), ("message", message), ("redirect", redirect), ("terms", terms)):
            self.db.execute("INSERT INTO portal_config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, v))
        self.db.commit()
        return "saved"

    @method()
    def SetFirewallPortRule(self, proto: "s", port: "u", action: "s") -> "s":
        if proto not in ("tcp", "udp") or not 1 <= port <= 65535 or action not in ("allow", "block"):
            raise ValueError("Invalid firewall rule")
        self.db.execute("INSERT INTO firewall_rules(proto,port,action) VALUES(?,?,?)", (proto, port, action))
        self.db.commit()
        self.apply_nft()
        return "saved"

    @method()
    def ListFirewallRules(self) -> "s":
        rows = [dict(zip(["id", "proto", "port", "action"], r)) for r in self.db.execute("SELECT id,proto,port,action FROM firewall_rules ORDER BY port")]
        return json.dumps(rows)

    @method()
    def RemoveFirewallRule(self, id: "u") -> "s":
        self.db.execute("DELETE FROM firewall_rules WHERE id=?", (id,))
        self.db.commit()
        self.apply_nft()
        return "removed"

    @method()
    def SetP2PBlocking(self, enabled: "b") -> "s":
        self.set_setting("p2p_blocking", "1" if enabled else "0")
        self.apply_nft()
        return "enabled" if enabled else "disabled"

    @method()
    def SetAdblockEnabled(self, enabled: "b") -> "s":
        self.set_setting("adblock_enabled", "1" if enabled else "0")
        return "enabled" if enabled else "disabled"

    @method()
    def GetAdblockStatus(self) -> "s":
        return json.dumps({
            "enabled": self.setting("adblock_enabled", "0") == "1",
            "count": int(self.setting("adblock_count", "0")),
            "updated": int(self.setting("adblock_updated", "0"))
        })

    @method()
    def UpdateAdblockList(self) -> "s":
        adblock_file = DATA / "dnsmasq-adblock.conf"
        hosts_url = "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts"
        try:
            import urllib.request
            req = urllib.request.Request(hosts_url, headers={"User-Agent": "LinuxHotspotManager/4.1"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
                count = 0
                with tempfile.NamedTemporaryFile("w", dir=DATA, delete=False) as tf:
                    for line in content.splitlines():
                        line = line.strip()
                        if line.startswith("0.0.0.0 ") or line.startswith("127.0.0.1 "):
                            parts = line.split()
                            if len(parts) >= 2:
                                domain = parts[1].strip()
                                if domain not in ("localhost", "local", "broadcasthost", "0.0.0.0"):
                                    tf.write(f"address=/{domain}/0.0.0.0\n")
                                    count += 1
                    temp_name = tf.name
                os.replace(temp_name, adblock_file)
                self.set_setting("adblock_count", str(count))
                self.set_setting("adblock_updated", str(int(time.time())))
                self.log("adblock", f"updated {count} blocked domains")
                run(["systemctl", "reload", "dnsmasq"])
                return json.dumps({"ok": True, "count": count})
        except Exception:
            default_ad_domains = [
                "doubleclick.net", "googleadservices.com", "googlesyndication.com",
                "adnxs.com", "ads.yahoo.com", "adservice.google.com",
                "advertising.com", "taboola.com", "outbrain.com",
                "scorecardresearch.com", "quantserve.com", "criteo.com",
                "popads.net", "propellerads.com", "zergnet.com",
                "adroll.com", "rubiconproject.com", "casalemedia.com"
            ]
            with tempfile.NamedTemporaryFile("w", dir=DATA, delete=False) as tf:
                for d in default_ad_domains:
                    tf.write(f"address=/{d}/0.0.0.0\n")
                temp_name = tf.name
            os.replace(temp_name, adblock_file)
            self.set_setting("adblock_count", str(len(default_ad_domains)))
            return json.dumps({"ok": True, "count": len(default_ad_domains), "fallback": True})

    @method()
    def ApplyBandwidthLimit(self, mac: "s", down_kbit: "u", up_kbit: "u") -> "s":
        if not valid_mac(mac):
            raise ValueError("Invalid MAC")
        self.SetBandwidthProfile(mac, down_kbit, up_kbit)
        iface = self.setting("hotspot_iface", "")
        if iface and valid_iface(iface):
            self._apply_tc(iface)
        return "applied"

    def _apply_tc(self, iface):
        run(["tc", "qdisc", "del", "dev", iface, "root"])
        total_kbit = self._int_setting("bandwidth_total_kbit", 0)
        clients = self.db.execute("SELECT mac, down_kbit, up_kbit FROM clients WHERE down_kbit > 0 OR up_kbit > 0").fetchall()
        if not clients and not total_kbit:
            return

        rate = f"{total_kbit}kbit" if total_kbit > 0 else "1000mbit"
        run(["tc", "qdisc", "add", "dev", iface, "root", "handle", "1:", "htb", "default", "99"])
        run(["tc", "class", "add", "dev", iface, "parent", "1:", "classid", "1:1", "htb", "rate", rate])
        run(["tc", "class", "add", "dev", iface, "parent", "1:1", "classid", "1:99", "htb", "rate", rate, "ceil", rate])

        for idx, (mac, down, up) in enumerate(clients, start=10):
            if down > 0:
                client_rate = f"{down}kbit"
                class_id = f"1:{idx}"
                run(["tc", "class", "add", "dev", iface, "parent", "1:1", "classid", class_id, "htb", "rate", client_rate, "ceil", client_rate])

    @method()
    def RebalanceBandwidth(self) -> "s":
        clients = self.db.execute("SELECT mac FROM clients WHERE blocked=0").fetchall()
        total = self._int_setting("bandwidth_total_kbit", 0)
        if not total or not clients:
            return "no-op"
        each = max(1, total // len(clients))
        for (mac,) in clients:
            self.db.execute("UPDATE clients SET down_kbit=?,up_kbit=? WHERE mac=?", (each, each, mac))
        self.db.commit()
        iface = self.setting("hotspot_iface", "")
        if iface and valid_iface(iface):
            self._apply_tc(iface)
        return str(each)

    @method()
    def ConfigureNetwork(self, mode: "s", gateway: "s", dhcp_range: "s", dns: "s", upstream: "s") -> "s":
        if mode not in ("router", "bridge", "repeater", "no-sharing", "ics"):
            raise ValueError("Invalid network mode")
        if not valid_ipv4(gateway):
            raise ValueError("Invalid gateway")
        self.set_setting("network_mode", mode)
        self.set_setting("gateway", gateway)
        self.set_setting("dhcp_range", dhcp_range)
        self.set_setting("dns", dns)
        self.set_setting("upstream_iface", upstream)
        return "saved"

    @method()
    def GetLogs(self) -> "s":
        rows = [dict(zip(["ts", "kind", "message"], r)) for r in self.db.execute("SELECT ts,kind,message FROM logs ORDER BY id DESC LIMIT 500")]
        return json.dumps(rows)

    @method()
    def GetUrlLog(self, count: "u") -> "s":
        limit = min(max(int(count), 1), 2000)
        dns_log_path = Path("/var/log/linux-hotspot-manager-dns.log")
        if dns_log_path.exists():
            try:
                lines = dns_log_path.read_text(errors="ignore").splitlines()[-limit:]
                for line in lines:
                    if "query[" in line and " from " in line:
                        parts = line.split("from")
                        client_ip = parts[1].strip().split()[0]
                        q_part = parts[0].split("query[")[1]
                        domain = q_part.split("]")[1].strip()
                        if domain and valid_domain(domain):
                            self.db.execute(
                                "INSERT OR IGNORE INTO url_logs(ts, mac, ip, url) VALUES(?,?,?,?)",
                                (int(time.time()), "", client_ip, domain)
                            )
                self.db.commit()
            except Exception:
                pass

        rows = self.db.execute(
            "SELECT id, ts, mac, ip, url FROM url_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return json.dumps([dict(zip(["id", "ts", "mac", "ip", "url"], r)) for r in rows])

    @method()
    def ClearUrlLogs(self) -> "s":
        self.db.execute("DELETE FROM url_logs")
        self.db.commit()
        dns_log_path = Path("/var/log/linux-hotspot-manager-dns.log")
        if dns_log_path.exists():
            try:
                dns_log_path.write_text("")
            except Exception:
                pass
        return "cleared"

    @method()
    def PurgeLogs(self, days: "u") -> "s":
        cutoff = int(time.time()) - int(days) * 86400
        self.db.execute("DELETE FROM logs WHERE ts<?", (cutoff,))
        self.db.execute("DELETE FROM url_logs WHERE ts<?", (cutoff,))
        self.db.commit()
        return "purged"

    @method()
    def ExportReport(self, fmt: "s") -> "s":
        if fmt not in ("json", "csv"):
            raise ValueError("Unsupported report format")
        rows = self.db.execute("SELECT ts,kind,message FROM logs ORDER BY id").fetchall()
        if fmt == "json":
            return json.dumps([{"ts": r[0], "kind": r[1], "message": r[2]} for r in rows])
        import csv
        import io
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["ts", "kind", "message"])
        w.writerows(rows)
        return out.getvalue()

    @method()
    def BackupDatabase(self) -> "s":
        dest = DATA / f"manager-backup-{int(time.time())}.sqlite3"
        b = sqlite3.connect(dest)
        self.db.backup(b)
        b.close()
        return str(dest)

    @method()
    def Diagnostics(self) -> "s":
        checks = {
            "nmcli": run(["nmcli", "-t", "general", "status"]).returncode == 0,
            "nft": run(["nft", "list", "tables"]).returncode == 0,
            "dnsmasq": run(["dnsmasq", "--version"]).returncode == 0,
            "ip_forward": Path("/proc/sys/net/ipv4/ip_forward").read_text().strip() if Path("/proc/sys/net/ipv4/ip_forward").exists() else "missing"
        }
        return json.dumps(checks)

    def _verify_password(self, encoded, password):
        try:
            alg, n, r, p, salt_hex, key_hex = encoded.split("$")
            if alg != "scrypt":
                return False
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(key_hex)
            actual = hashlib.scrypt(password.encode(), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
            return secrets.compare_digest(actual, expected)
        except Exception:
            return False

    @method()
    def AuthenticatePortalClient(self, interface: "s", mac: "s", username: "s", password: "s", ttl: "u") -> "s":
        if not valid_iface(interface) or not valid_mac(mac):
            raise ValueError("Invalid client identity")
        now = int(time.time())
        token = secrets.token_urlsafe(32)
        expires = now + min(max(int(ttl), 60), 86400)
        ok = False
        subject = username or "terms"
        if username:
            row = self.db.execute("SELECT password_hash,enabled,expires_at FROM users WHERE username=?", (username,)).fetchone()
            if row and row[1] and (not row[2] or row[2] >= now) and self._verify_password(row[0], password):
                ok = True
        if not ok and username:
            vr = self.db.execute("SELECT expires_at,used FROM vouchers WHERE code=?", (username.upper(),)).fetchone()
            if vr and not vr[1] and (not vr[0] or vr[0] >= now):
                self.db.execute("UPDATE vouchers SET used=1,used_by=? WHERE code=?", (mac.lower(), username.upper()))
                self.db.commit()
                ok = True
                subject = "voucher:" + username.upper()
        if not ok:
            raise ValueError("Authentication failed")
        self.db.execute("INSERT INTO sessions(username,mac,ip,started_at) VALUES(?,?,?,?)", (subject, mac.lower(), "", now))
        self.db.commit()
        sessions = _load_portal_sessions()
        sessions[mac.lower()] = {"token": token, "authenticated": True, "interface": interface, "username": subject, "expires_at": expires}
        _save_portal_sessions(sessions)
        self.set_setting("portal_session:" + token, json.dumps({"mac": mac.lower(), "interface": interface, "username": subject, "expires_at": expires}))
        self.log("portal", f"authenticated {mac.lower()} as {subject}")
        return json.dumps({"ok": True, "token": token, "expires_at": expires})

    @method()
    def AcceptPortalTerms(self, interface: "s", mac: "s", ttl: "u") -> "s":
        if not valid_iface(interface) or not valid_mac(mac):
            raise ValueError("Invalid client identity")
        token = secrets.token_urlsafe(32)
        expires = int(time.time()) + min(max(int(ttl), 60), 86400)
        sessions = _load_portal_sessions()
        sessions[mac.lower()] = {"token": token, "authenticated": True, "interface": interface, "username": "terms", "expires_at": expires}
        _save_portal_sessions(sessions)
        self.set_setting("portal_session:" + token, json.dumps({"mac": mac.lower(), "interface": interface, "username": "terms", "expires_at": expires}))
        self.log("portal", f"terms accepted by {mac.lower()}")
        return json.dumps({"ok": True, "token": token, "expires_at": expires})

    @method()
    def ValidatePortalSession(self, token: "s", mac: "s") -> "b":
        if not valid_mac(mac):
            return False
        return _portal_session_valid(mac, token)

    @method()
    def RevokePortalSession(self, token: "s") -> "b":
        self.set_setting("portal_session:" + token, json.dumps({"revoked": True}))
        sessions = _load_portal_sessions()
        for k, v in list(sessions.items()):
            if v.get("token") == token:
                sessions.pop(k, None)
        _save_portal_sessions(sessions)
        return True

    @method()
    def GetPortalConfig(self) -> "s":
        return json.dumps({k: v for k, v in self.db.execute("SELECT key,value FROM portal_config")})

    @method()
    def AddFreeUrl(self, domain: "s") -> "s":
        domain = domain.lower().rstrip(".")
        if not valid_domain(domain):
            raise ValueError("Invalid domain")
        self.db.execute("INSERT OR IGNORE INTO free_urls(domain) VALUES(?)", (domain,))
        self.db.commit()
        return "saved"

    @method()
    def SetMacRule(self, mac: "s", action: "s") -> "s":
        if not valid_mac(mac) or action not in ("allow", "block"):
            raise ValueError("Invalid MAC rule")
        self.db.execute("INSERT INTO mac_rules(mac,action) VALUES(?,?) ON CONFLICT(mac) DO UPDATE SET action=excluded.action", (mac.lower(), action))
        self.db.commit()
        self.apply_nft()
        return "saved"

    @method()
    def AddPortForward(self, proto: "s", listen_port: "u", destination_ip: "s", destination_port: "u") -> "s":
        if proto not in ("tcp", "udp") or not 1 <= listen_port <= 65535 or not 1 <= destination_port <= 65535 or not valid_ipv4(destination_ip):
            raise ValueError("Invalid port forward")
        self.set_setting(f"portforward:{proto}:{listen_port}", json.dumps({"destination_ip": destination_ip, "destination_port": destination_port}))
        self.apply_nft()
        return "saved"

    @method()
    def ListPortForwards(self) -> "s":
        rows = []
        for key, val in self.db.execute("SELECT key, value FROM settings WHERE key LIKE 'portforward:%'"):
            parts = key.split(":")
            if len(parts) >= 3:
                proto = parts[1]
                listen = int(parts[2])
                try:
                    data = json.loads(val)
                    rows.append({
                        "proto": proto,
                        "listen_port": listen,
                        "destination_ip": data.get("destination_ip", ""),
                        "destination_port": data.get("destination_port", 0)
                    })
                except Exception:
                    pass
        return json.dumps(rows)

    @method()
    def DeletePortForward(self, proto: "s", listen_port: "u") -> "s":
        self.db.execute("DELETE FROM settings WHERE key=?", (f"portforward:{proto}:{listen_port}",))
        self.db.commit()
        self.apply_nft()
        return "deleted"

    @method()
    def ApplyPortForwards(self) -> "s":
        self.apply_nft()
        return "applied"

    @method()
    def SetFeatureConfig(self, group: "s", payload: "s") -> "s":
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", group):
            raise ValueError("Invalid feature group")
        if len(payload) > 100000:
            raise ValueError("Configuration too large")
        try:
            json.loads(payload)
        except Exception:
            raise ValueError("Invalid JSON configuration")
        self.set_setting("feature:" + group, payload)
        self.log("config", f"updated {group}")
        return "saved"

    @method()
    def SetUserEnabled(self, username: "s", enabled: "b") -> "s":
        self.db.execute("UPDATE users SET enabled=? WHERE username=?", (int(enabled), username))
        if self.db.total_changes == 0:
            raise ValueError("User not found")
        self.db.commit()
        self.log("user", f"{username}: {'enabled' if enabled else 'disabled'}")
        return "saved"

    @method()
    def DeleteUser(self, username: "s") -> "s":
        self.db.execute("DELETE FROM users WHERE username=?", (username,))
        if self.db.total_changes == 0:
            raise ValueError("User not found")
        self.db.commit()
        self.log("user", f"deleted {username}")
        return "deleted"

    @method()
    def SetPricing(self, name: "s", price: "d", duration: "u", data_quota: "t", down_kbit: "u", up_kbit: "u") -> "s":
        if not name or len(name) > 128 or price < 0 or duration > 315360000 or down_kbit > 10000000 or up_kbit > 10000000:
            raise ValueError("Invalid pricing package")
        self.db.execute("INSERT INTO pricing(name,price,duration,data_quota,down_kbit,up_kbit) VALUES(?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET price=excluded.price,duration=excluded.duration,data_quota=excluded.data_quota,down_kbit=excluded.down_kbit,up_kbit=excluded.up_kbit",
                        (name, price, duration, data_quota, down_kbit, up_kbit))
        self.db.commit()
        self.log("pricing", f"saved {name}")
        return "saved"

    @method()
    def ListPricing(self) -> "s":
        rows = [dict(zip(["id", "name", "price", "duration", "data_quota", "down_kbit", "up_kbit"], r)) for r in self.db.execute("SELECT id,name,price,duration,data_quota,down_kbit,up_kbit FROM pricing ORDER BY name")]
        return json.dumps(rows)

    @method()
    def CreateStaff(self, username: "s", password: "s", role: "s") -> "s":
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", username) or len(password) < 8 or role not in ("admin", "manager", "operator", "viewer"):
            raise ValueError("Invalid staff account")
        self.db.execute("INSERT INTO staff(username,password_hash,role) VALUES(?,?,?)", (username, hash_password(password), role))
        self.db.commit()
        self.log("staff", f"created {username}")
        return "created"

    @method()
    def ListStaff(self) -> "s":
        rows = [dict(zip(["id", "username", "role", "enabled"], r)) for r in self.db.execute("SELECT id,username,role,enabled FROM staff ORDER BY username")]
        return json.dumps(rows)

    @method()
    def ListInterfaces(self) -> "s":
        r = run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"])
        rows = []
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                p = line.split(":")
                if len(p) >= 3 and valid_iface(p[0]):
                    rows.append({"device": p[0], "type": p[1], "state": p[2]})
        return json.dumps(rows)

    def _get_clients(self):
        lease_files = ["/var/lib/misc/dnsmasq.leases", "/run/dnsmasq.leases", "/var/lib/NetworkManager/dnsmasq-*.leases"]
        rows = []
        for f_pat in lease_files:
            import glob
            for f in glob.glob(f_pat):
                if not os.path.exists(f):
                    continue
                for line in Path(f).read_text(errors="ignore").splitlines():
                    p = line.split()
                    if len(p) >= 4 and valid_mac(p[1]) and valid_ipv4(p[2]):
                        rows.append({"mac": p[1].lower(), "ip": p[2], "hostname": "" if p[3] == "*" else p[3]})
                if rows:
                    break
            if rows:
                break
        return rows

    @method()
    def GetClients(self) -> "s":
        return json.dumps(self._get_clients())

    @method()
    def GetClientTraffic(self, iface: "s") -> "s":
        clients = self._get_clients()
        counters = {c["mac"]: c for c in _parse_client_counters(iface)}
        stored = {r[0].lower(): (r[1], r[2], r[3]) for r in self.db.execute("SELECT mac, blocked, down_kbit, up_kbit FROM clients")}

        out = []
        for c in clients:
            mac = c["mac"].lower()
            cnt = counters.get(mac, {})
            st = stored.get(mac, (0, 0, 0))
            out.append({
                "mac": mac,
                "ip": c.get("ip", ""),
                "hostname": c.get("hostname", ""),
                "rx_bytes": cnt.get("rx_bytes", 0),
                "tx_bytes": cnt.get("tx_bytes", 0),
                "packets_rx": cnt.get("packets_rx", 0),
                "packets_tx": cnt.get("packets_tx", 0),
                "blocked": bool(st[0]),
                "down_kbit": st[1],
                "up_kbit": st[2]
            })
        return json.dumps(out)

async def main():
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    bus.export(PATH, Manager())
    await bus.request_name(SERVICE)
    await asyncio.get_running_loop().create_future()

if __name__ == "__main__":
    asyncio.run(main())
