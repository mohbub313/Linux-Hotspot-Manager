#!/usr/bin/env python3
"""
Linux Hotspot Manager GTK4 / Libadwaita Administration Console.
A complete, modern Linux clone of MyPublicWiFi for Parrot OS / Debian KDE.

Features:
1. General & Network Setup (SSID, WPA2, Internet Source, Wi-Fi Adapter, Modes, One-Click Start/Stop)
2. Connected Clients & Bandwidth (Live table with IP, MAC, Hostname, Download/Upload MB, Speed Limits, Block/Unblock)
3. Firewall & Security (P2P/Torrent Blocking, Port Blocking, Domain Blacklisting, LAN Isolation)
4. Bandwidth & Adblocker (DNS Adblocker with Steven Black hostlist, Global Speed Limit, Fair-Share Rebalance)
5. Captive Portal (Free Access, Terms Acceptance, User Accounts, Vouchers, Custom Branding)
6. Management, URL Logs & Port Forwarding (DNS Query Logger, Virtual Server Port Forwarding, 12 Languages, Diagnostics)
"""
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk

try:
    from dbus_next.glib import MessageBus
    from dbus_next import BusType
except Exception:
    MessageBus = None

# Add src to path for i18n
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from i18n import i18n, _, SUPPORTED_LANGUAGES

SERVICE = "com.shazid.LinuxHotspotManager"
PATH = "/com/shazid/LinuxHotspotManager"
IFACE = SERVICE

CUSTOM_CSS = """
/* Modern sleek styling for Linux Hotspot Manager */
window {
    background-color: #0f172a;
}
.sidebar-pane {
    background-color: #1e293b;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
}
.status-card {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 16px;
}
.status-pill {
    padding: 4px 14px;
    border-radius: 9999px;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 0.5px;
}
.status-active {
    background-color: rgba(16, 185, 129, 0.2);
    color: #34d399;
    border: 1px solid #10b981;
}
.status-stopped {
    background-color: rgba(239, 68, 68, 0.2);
    color: #f87171;
    border: 1px solid #ef4444;
}
.btn-start {
    background: linear-gradient(135deg, #10b981, #059669);
    color: white;
    font-weight: 700;
    font-size: 15px;
    padding: 12px 28px;
    border-radius: 12px;
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.4);
}
.btn-start:hover {
    background: linear-gradient(135deg, #059669, #047857);
}
.btn-stop {
    background: linear-gradient(135deg, #ef4444, #dc2626);
    color: white;
    font-weight: 700;
    font-size: 15px;
    padding: 12px 28px;
    border-radius: 12px;
    box-shadow: 0 4px 14px rgba(239, 68, 68, 0.4);
}
.btn-stop:hover {
    background: linear-gradient(135deg, #dc2626, #b91c1c);
}
.badge-count {
    background-color: #3b82f6;
    color: white;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 700;
}
.dim-desc {
    color: #94a3b8;
    font-size: 13px;
}
.table-header {
    font-weight: 700;
    color: #94a3b8;
    font-size: 12px;
    text-transform: uppercase;
    padding: 8px 12px;
    background: rgba(15, 23, 42, 0.5);
    border-radius: 8px;
}
.client-row {
    background: #1e293b;
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: 6px;
    border: 1px solid rgba(255, 255, 255, 0.05);
}
.log-box {
    background: #090d16;
    font-family: monospace;
    font-size: 12px;
    border-radius: 10px;
    padding: 12px;
    color: #38bdf8;
    border: 1px solid rgba(255, 255, 255, 0.08);
}
"""

def format_bytes(b):
    b = float(b or 0)
    if b < 1024:
        return f"{int(b)} B"
    elif b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    elif b < 1024 * 1024 * 1024:
        return f"{b / (1024 * 1024):.1f} MB"
    else:
        return f"{b / (1024 * 1024 * 1024):.2f} GB"

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("app_title"))
        self.set_default_size(1180, 780)
        self.set_size_request(900, 600)

        # Load CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(CUSTOM_CSS.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # State
        self.hotspot_running = False
        self.active_iface = ""
        self.detected_devices = []
        self.clients_data = []
        self.url_logs_data = []

        # Toast overlay
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        # Main Split / Layout
        split_view = Adw.NavigationSplitView()
        split_view.set_min_sidebar_width(240)
        split_view.set_max_sidebar_width(280)
        self.toast_overlay.set_child(split_view)

        # Sidebar Page
        sidebar_page = Adw.NavigationPage.new(self.build_sidebar(), _("app_title"))
        split_view.set_sidebar(sidebar_page)

        # Content ViewStack
        self.stack = Adw.ViewStack()
        content_page = Adw.NavigationPage.new(self.stack, _("app_title"))
        split_view.set_content(content_page)

        # Register pages in stack
        self.build_pages()

        # Connect i18n reload
        i18n.add_listener(self.on_language_changed)

        # Initial data loading
        GLib.idle_add(self.initial_load)

        # Polling timer (3 seconds)
        GLib.timeout_add_seconds(3, self.poll_status)

    def toast(self, msg):
        toast = Adw.Toast.new(msg)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)

    def call_dbus(self, method, *args, cb=None):
        """Asynchronously call D-Bus service without blocking UI."""
        if MessageBus is None:
            self.toast("dbus_next is not available")
            return

        def worker():
            try:
                bus = MessageBus(bus_type=BusType.SYSTEM).connect_sync()
                obj = bus.get_proxy_object(SERVICE, PATH, bus.introspect_sync(SERVICE, PATH))
                iface = obj.get_interface(IFACE)
                py_method = re.sub(r"(?<!^)(?=[A-Z])", "_", method).lower()
                func = getattr(iface, f"call_{py_method}_sync")
                res = func(*args)
                bus.disconnect()
                if cb:
                    GLib.idle_add(cb, res)
            except Exception as e:
                err = str(e)
                GLib.idle_add(lambda: self.toast(f"D-Bus Error: {err}"))

        threading.Thread(target=worker, daemon=True).start()

    def build_sidebar(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.add_css_class("sidebar-pane")

        # Header with app icon and title
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header_box.set_margin_top(16)
        header_box.set_margin_bottom(16)
        header_box.set_margin_start(16)
        header_box.set_margin_end(16)

        icon = Gtk.Image.new_from_icon_name("network-wireless-symbolic")
        icon.set_pixel_size(24)
        header_box.append(icon)

        title_label = Gtk.Label(label="Hotspot Manager", xalign=0)
        title_label.add_css_class("title-3")
        header_box.append(title_label)
        box.append(header_box)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.append(sep)

        # Nav List Box
        self.nav_list = Gtk.ListBox()
        self.nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nav_list.add_css_class("navigation-sidebar")
        self.nav_list.set_vexpand(True)

        self.nav_items = [
            ("general", _("tab_general"), "network-wireless-hotspot-symbolic"),
            ("clients", _("tab_clients"), "system-users-symbolic"),
            ("firewall", _("tab_firewall"), "security-high-symbolic"),
            ("bandwidth", _("tab_bandwidth"), "speedometer-symbolic"),
            ("portal", _("tab_portal"), "web-browser-symbolic"),
            ("management", _("tab_management"), "preferences-system-symbolic"),
        ]

        self.nav_rows = {}
        for tag, title, icon_name in self.nav_items:
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row_box.set_margin_top(10)
            row_box.set_margin_bottom(10)
            row_box.set_margin_start(14)
            row_box.set_margin_end(14)

            ic = Gtk.Image.new_from_icon_name(icon_name)
            ic.set_pixel_size(18)
            row_box.append(ic)

            lbl = Gtk.Label(label=title, xalign=0)
            lbl.set_hexpand(True)
            row_box.append(lbl)

            if tag == "clients":
                self.clients_badge = Gtk.Label(label="0")
                self.clients_badge.add_css_class("badge-count")
                self.clients_badge.set_visible(False)
                row_box.append(self.clients_badge)

            row.set_child(row_box)
            self.nav_list.append(row)
            self.nav_rows[tag] = (row, lbl)

        self.nav_list.connect("row-selected", self.on_nav_selected)
        box.append(self.nav_list)

        # Bottom language selector
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom_box.set_margin_top(12)
        bottom_box.set_margin_bottom(12)
        bottom_box.set_margin_start(12)
        bottom_box.set_margin_end(12)

        lang_icon = Gtk.Image.new_from_icon_name("preferences-desktop-locale-symbolic")
        bottom_box.append(lang_icon)

        lang_codes = list(SUPPORTED_LANGUAGES.keys())
        lang_names = [SUPPORTED_LANGUAGES[k] for k in lang_codes]
        self.lang_dropdown = Gtk.DropDown.new_from_strings(lang_names)
        self.lang_dropdown.set_hexpand(True)
        cur_idx = lang_codes.index(i18n.current_lang) if i18n.current_lang in lang_codes else 0
        self.lang_dropdown.set_selected(cur_idx)
        self.lang_dropdown.connect("notify::selected", self.on_lang_dropdown_changed)
        bottom_box.append(self.lang_dropdown)

        box.append(bottom_box)
        return box

    def on_nav_selected(self, listbox, row):
        if not row:
            return
        idx = row.get_index()
        if 0 <= idx < len(self.nav_items):
            tag = self.nav_items[idx][0]
            self.stack.set_visible_child_name(tag)

    def on_lang_dropdown_changed(self, dropdown, _param):
        idx = dropdown.get_selected()
        lang_codes = list(SUPPORTED_LANGUAGES.keys())
        if 0 <= idx < len(lang_codes):
            code = lang_codes[idx]
            if code != i18n.current_lang:
                i18n.load_language(code)
                self.call_dbus("SetFeatureConfig", "settings", json.dumps({"language": code}))

    def on_language_changed(self):
        # Refresh sidebar labels
        for tag, (_row, lbl) in self.nav_rows.items():
            key = f"tab_{tag}"
            lbl.set_text(_(key))
        self.toast(_("success"))

    def build_pages(self):
        # 1. General & Hotspot Setup
        self.stack.add_named(self.build_page_general(), "general")
        # 2. Connected Clients
        self.stack.add_named(self.build_page_clients(), "clients")
        # 3. Firewall & Security
        self.stack.add_named(self.build_page_firewall(), "firewall")
        # 4. Bandwidth & Adblocker
        self.stack.add_named(self.build_page_bandwidth(), "bandwidth")
        # 5. Captive Portal
        self.stack.add_named(self.build_page_portal(), "portal")
        # 6. Management & Logs
        self.stack.add_named(self.build_page_management(), "management")

        # Select first row by default
        first_row = self.nav_rows["general"][0]
        self.nav_list.select_row(first_row)

    # -------------------------------------------------------------
    # PAGE 1: Hotspot & General Setup
    # -------------------------------------------------------------
    def build_page_general(self):
        scroll = Gtk.ScrolledWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)
        scroll.set_child(box)

        # Status & Toggle Header Card
        status_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        status_card.add_css_class("status-card")

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        info_box.set_hexpand(True)

        pill_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.status_pill = Gtk.Label(label=_("hotspot_stopped"))
        self.status_pill.add_css_class("status-pill")
        self.status_pill.add_css_class("status-stopped")
        pill_box.append(self.status_pill)
        info_box.append(pill_box)

        self.status_desc = Gtk.Label(label="Virtual Wi-Fi Access Point is offline", xalign=0)
        self.status_desc.add_css_class("dim-desc")
        info_box.append(self.status_desc)

        status_card.append(info_box)

        self.toggle_btn = Gtk.Button(label=_("start_hotspot"))
        self.toggle_btn.add_css_class("btn-start")
        self.toggle_btn.connect("clicked", self.on_toggle_hotspot)
        status_card.append(self.toggle_btn)
        box.append(status_card)

        # Preferences Group: Network Configuration
        group = Adw.PreferencesGroup()
        group.set_title(_("general_settings"))
        group.set_description("Configure broadcast SSID, WPA2 security key, and internet sharing source.")

        # SSID Row
        self.row_ssid = Adw.EntryRow()
        self.row_ssid.set_title(_("ssid"))
        self.row_ssid.set_text("LinuxHotspot")
        group.add(self.row_ssid)

        # Password Row
        self.row_pass = Adw.PasswordEntryRow()
        self.row_pass.set_title(_("password"))
        self.row_pass.set_text("12345678")
        group.add(self.row_pass)

        # Internet Connection Dropdown
        self.row_inet = Adw.ComboRow()
        self.row_inet.set_title(_("internet_source"))
        self.inet_model = Gtk.StringList()
        self.row_inet.set_model(self.inet_model)
        group.add(self.row_inet)

        # Wi-Fi Adapter Dropdown
        self.row_adapter = Adw.ComboRow()
        self.row_adapter.set_title(_("wifi_adapter"))
        self.adapter_model = Gtk.StringList()
        self.row_adapter.set_model(self.adapter_model)
        group.add(self.row_adapter)

        # Hosted Network Mode Dropdown
        self.row_mode = Adw.ComboRow()
        self.row_mode.set_title(_("network_mode"))
        self.mode_model = Gtk.StringList.new([
            _("mode_router"),
            _("mode_bridge"),
            _("mode_repeater"),
            _("mode_no_sharing")
        ])
        self.row_mode.set_model(self.mode_model)
        group.add(self.row_mode)

        # Hidden SSID Switch
        self.row_hidden = Adw.SwitchRow()
        self.row_hidden.set_title(_("hidden_ssid"))
        group.add(self.row_hidden)

        box.append(group)
        return scroll

    def on_toggle_hotspot(self, btn):
        if not self.hotspot_running:
            ssid = self.row_ssid.get_text().strip() or "LinuxHotspot"
            psk = self.row_pass.get_text().strip()
            if len(psk) < 8:
                self.toast("Password must be at least 8 characters")
                return
            btn.set_sensitive(False)
            btn.set_label(_("starting"))
            self.call_dbus("StartHotspot", ssid, psk, cb=self.on_hotspot_started)
        else:
            ssid = self.row_ssid.get_text().strip() or "LinuxHotspot"
            btn.set_sensitive(False)
            btn.set_label(_("stopping"))
            self.call_dbus("StopHotspot", ssid, cb=self.on_hotspot_stopped)

    def on_hotspot_started(self, res):
        self.toggle_btn.set_sensitive(True)
        self.hotspot_running = True
        self.update_status_ui()
        self.toast("Hotspot started successfully!")

    def on_hotspot_stopped(self, res):
        self.toggle_btn.set_sensitive(True)
        self.hotspot_running = False
        self.update_status_ui()
        self.toast("Hotspot stopped")

    def update_status_ui(self):
        if self.hotspot_running:
            self.status_pill.set_text(_("hotspot_active"))
            self.status_pill.remove_css_class("status-stopped")
            self.status_pill.add_css_class("status-active")
            self.status_desc.set_text(f"Broadcasting SSID: {self.row_ssid.get_text()}")
            self.toggle_btn.set_label(_("stop_hotspot"))
            self.toggle_btn.remove_css_class("btn-start")
            self.toggle_btn.add_css_class("btn-stop")
        else:
            self.status_pill.set_text(_("hotspot_stopped"))
            self.status_pill.remove_css_class("status-active")
            self.status_pill.add_css_class("status-stopped")
            self.status_desc.set_text("Virtual Wi-Fi Access Point is offline")
            self.toggle_btn.set_label(_("start_hotspot"))
            self.toggle_btn.remove_css_class("btn-stop")
            self.toggle_btn.add_css_class("btn-start")

    # -------------------------------------------------------------
    # PAGE 2: Connected Clients & Traffic
    # -------------------------------------------------------------
    def build_page_clients(self):
        scroll = Gtk.ScrolledWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)
        scroll.set_child(box)

        # Header toolbar
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        h = Gtk.Label(label=_("clients_title"), xalign=0)
        h.add_css_class("title-2")
        h.set_hexpand(True)
        tb.append(h)

        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text(_("refresh"))
        refresh_btn.connect("clicked", lambda _: self.refresh_clients())
        tb.append(refresh_btn)
        box.append(tb)

        desc = Gtk.Label(label=_("clients_desc"), xalign=0)
        desc.add_css_class("dim-desc")
        box.append(desc)

        # Clients Container
        self.clients_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.clients_empty = Gtk.Label(label=_("no_clients"))
        self.clients_empty.add_css_class("dim-desc")
        self.clients_empty.set_margin_top(40)
        self.clients_container.append(self.clients_empty)

        box.append(self.clients_container)
        return scroll

    def refresh_clients(self):
        self.call_dbus("GetClientTraffic", self.active_iface or "wlan0", cb=self.on_clients_data)

    def on_clients_data(self, res):
        try:
            clients = json.loads(res)
        except Exception:
            clients = []
        self.clients_data = clients

        # Update sidebar badge
        count = len(clients)
        if count > 0:
            self.clients_badge.set_text(str(count))
            self.clients_badge.set_visible(True)
        else:
            self.clients_badge.set_visible(False)

        # Clear existing
        while child := self.clients_container.get_first_child():
            self.clients_container.remove(child)

        if not clients:
            self.clients_container.append(self.clients_empty)
            return

        # Header Row
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hdr.add_css_class("table-header")
        col_dev = Gtk.Label(label=_("client_hostname"), xalign=0); col_dev.set_hexpand(True); hdr.append(col_dev)
        col_ip = Gtk.Label(label=_("client_ip"), xalign=0); col_ip.set_size_request(130, -1); hdr.append(col_ip)
        col_mac = Gtk.Label(label=_("client_mac"), xalign=0); col_mac.set_size_request(140, -1); hdr.append(col_mac)
        col_rx = Gtk.Label(label=_("client_download"), xalign=1); col_rx.set_size_request(90, -1); hdr.append(col_rx)
        col_tx = Gtk.Label(label=_("client_upload"), xalign=1); col_tx.set_size_request(90, -1); hdr.append(col_tx)
        col_act = Gtk.Label(label="Actions", xalign=0); col_act.set_size_request(150, -1); hdr.append(col_act)
        self.clients_container.append(hdr)

        for c in clients:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.add_css_class("client-row")

            # Hostname & icon
            name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            name_box.set_hexpand(True)
            ic = Gtk.Image.new_from_icon_name("computer-symbolic")
            name_box.append(ic)
            name_lbl = Gtk.Label(label=c.get("hostname") or "Unknown Device", xalign=0)
            name_lbl.set_ellipsize(3) # Pango.EllipsizeMode.END
            name_box.append(name_lbl)
            row.append(name_box)

            # IP
            ip_lbl = Gtk.Label(label=c.get("ip", ""), xalign=0)
            ip_lbl.set_size_request(130, -1)
            row.append(ip_lbl)

            # MAC
            mac_lbl = Gtk.Label(label=c.get("mac", ""), xalign=0)
            mac_lbl.add_css_class("monospace")
            mac_lbl.set_size_request(140, -1)
            row.append(mac_lbl)

            # RX / TX
            rx_lbl = Gtk.Label(label=format_bytes(c.get("rx_bytes", 0)), xalign=1)
            rx_lbl.set_size_request(90, -1)
            row.append(rx_lbl)

            tx_lbl = Gtk.Label(label=format_bytes(c.get("tx_bytes", 0)), xalign=1)
            tx_lbl.set_size_request(90, -1)
            row.append(tx_lbl)

            # Actions
            act_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            act_box.set_size_request(150, -1)

            # Block / Unblock Button
            is_blocked = c.get("blocked", False)
            blk_btn = Gtk.Button(label=_("action_unblock") if is_blocked else _("action_block"))
            if is_blocked:
                blk_btn.add_css_class("suggested-action")
            else:
                blk_btn.add_css_class("destructive-action")
            blk_btn.connect("clicked", lambda _, m=c["mac"], b=not is_blocked: self.toggle_block_client(m, b))
            act_box.append(blk_btn)

            # Limit speed button
            lim_btn = Gtk.Button(label=_("action_limit"))
            lim_btn.connect("clicked", lambda _, m=c["mac"], d=c.get("down_kbit", 0), u=c.get("up_kbit", 0): self.show_speed_limit_dialog(m, d, u))
            act_box.append(lim_btn)

            row.append(act_box)
            self.clients_container.append(row)

    def toggle_block_client(self, mac, blocked):
        self.call_dbus("SetClientBlocked", mac, blocked, cb=lambda _: self.refresh_clients())

    def show_speed_limit_dialog(self, mac, cur_down, cur_up):
        dialog = Adw.AlertDialog.new(_("dialog_limit_speed"), f"Set bandwidth throttling for {mac}")
        dialog.add_response("cancel", _("cancel"))
        dialog.add_response("save", _("save"))
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12); box.set_margin_bottom(12)

        down_entry = Adw.EntryRow()
        down_entry.set_title(_("down_kbit"))
        down_entry.set_text(str(cur_down))
        box.append(down_entry)

        up_entry = Adw.EntryRow()
        up_entry.set_title(_("up_kbit"))
        up_entry.set_text(str(cur_up))
        box.append(up_entry)

        dialog.set_extra_child(box)

        def on_response(_d, response):
            if response == "save":
                try:
                    d = int(down_entry.get_text() or 0)
                    u = int(up_entry.get_text() or 0)
                    self.call_dbus("ApplyBandwidthLimit", mac, d, u, cb=lambda _: self.refresh_clients())
                except ValueError:
                    self.toast("Invalid numbers")

        dialog.connect("response", on_response)
        dialog.present(self)

    # -------------------------------------------------------------
    # PAGE 3: Firewall & Security Options
    # -------------------------------------------------------------
    def build_page_firewall(self):
        scroll = Gtk.ScrolledWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20); box.set_margin_bottom(24); box.set_margin_start(24); box.set_margin_end(24)
        scroll.set_child(box)

        h = Gtk.Label(label=_("firewall_title"), xalign=0)
        h.add_css_class("title-2")
        box.append(h)

        # General Security Toggles
        sec_grp = Adw.PreferencesGroup()
        sec_grp.set_title("Network Protection Rules")

        self.sw_p2p = Adw.SwitchRow()
        self.sw_p2p.set_title(_("p2p_block"))
        self.sw_p2p.set_subtitle(_("p2p_block_desc"))
        self.sw_p2p.connect("notify::active", self.on_p2p_toggled)
        sec_grp.add(self.sw_p2p)

        self.sw_lan = Adw.SwitchRow()
        self.sw_lan.set_title(_("lan_block"))
        self.sw_lan.set_subtitle(_("lan_block_desc"))
        self.sw_lan.connect("notify::active", self.on_lan_toggled)
        sec_grp.add(self.sw_lan)

        box.append(sec_grp)

        # Blocked Ports Group
        self.ports_grp = Adw.PreferencesGroup()
        self.ports_grp.set_title(_("port_rules"))
        self.ports_grp.set_description(_("port_rules_desc"))

        add_port_btn = Gtk.Button(label=_("add_port"))
        add_port_btn.add_css_class("suggested-action")
        add_port_btn.connect("clicked", lambda _: self.show_add_port_dialog())
        self.ports_grp.set_header_suffix(add_port_btn)

        self.ports_rows_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.ports_grp.add(self.ports_rows_container)
        box.append(self.ports_grp)

        # Domain Blacklist Group
        self.domains_grp = Adw.PreferencesGroup()
        self.domains_grp.set_title(_("domain_blacklist"))
        self.domains_grp.set_description(_("domain_blacklist_desc"))

        add_dom_btn = Gtk.Button(label=_("add_domain"))
        add_dom_btn.add_css_class("suggested-action")
        add_dom_btn.connect("clicked", lambda _: self.show_add_domain_dialog())
        self.domains_grp.set_header_suffix(add_dom_btn)

        self.domains_rows_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.domains_grp.add(self.domains_rows_container)
        box.append(self.domains_grp)

        return scroll

    def on_p2p_toggled(self, sw, _param):
        self.call_dbus("SetP2PBlocking", sw.get_active(), cb=lambda _: self.toast("P2P blocking updated"))

    def on_lan_toggled(self, sw, _param):
        self.call_dbus("SetFeatureConfig", "firewall", json.dumps({"lan_block": sw.get_active()}))

    def refresh_firewall_rules(self):
        self.call_dbus("ListFirewallRules", cb=self.on_ports_data)
        self.call_dbus("ListDomainRules", cb=self.on_domains_data)

    def on_ports_data(self, res):
        try:
            rules = json.loads(res)
        except Exception:
            rules = []
        while child := self.ports_rows_container.get_first_child():
            self.ports_rows_container.remove(child)

        for r in rules:
            row = Adw.ActionRow()
            row.set_title(f"{r['proto'].upper()} Port {r['port']}")
            row.set_subtitle(f"Action: {r['action'].upper()}")
            del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
            del_btn.add_css_class("flat")
            del_btn.add_css_class("destructive-action")
            del_btn.connect("clicked", lambda _, rid=r["id"]: self.call_dbus("RemoveFirewallRule", rid, cb=lambda _: self.refresh_firewall_rules()))
            row.add_suffix(del_btn)
            self.ports_rows_container.append(row)

    def on_domains_data(self, res):
        try:
            rules = json.loads(res)
        except Exception:
            rules = []
        while child := self.domains_rows_container.get_first_child():
            self.domains_rows_container.remove(child)

        for d in rules:
            row = Adw.ActionRow()
            row.set_title(d["domain"])
            row.set_subtitle(f"Action: {d['action'].upper()}")
            del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
            del_btn.add_css_class("flat")
            del_btn.add_css_class("destructive-action")
            del_btn.connect("clicked", lambda _, dom=d["domain"]: self.call_dbus("RemoveDomainRule", dom, cb=lambda _: self.refresh_firewall_rules()))
            row.add_suffix(del_btn)
            self.domains_rows_container.append(row)

    def show_add_port_dialog(self):
        dialog = Adw.AlertDialog.new(_("dialog_add_port"), "Block an outbound destination port")
        dialog.add_response("cancel", _("cancel"))
        dialog.add_response("add", _("add"))
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(10); box.set_margin_bottom(10)

        proto_combo = Adw.ComboRow()
        proto_combo.set_title(_("protocol"))
        proto_combo.set_model(Gtk.StringList.new(["TCP", "UDP"]))
        box.append(proto_combo)

        port_entry = Adw.EntryRow()
        port_entry.set_title(_("port"))
        box.append(port_entry)

        dialog.set_extra_child(box)

        def on_resp(_d, resp):
            if resp == "add":
                p_str = port_entry.get_text().strip()
                proto = "tcp" if proto_combo.get_selected() == 0 else "udp"
                if p_str.isdigit() and 1 <= int(p_str) <= 65535:
                    self.call_dbus("SetFirewallPortRule", proto, int(p_str), "block", cb=lambda _: self.refresh_firewall_rules())
                else:
                    self.toast("Invalid port number (1-65535)")

        dialog.connect("response", on_resp)
        dialog.present(self)

    def show_add_domain_dialog(self):
        dialog = Adw.AlertDialog.new(_("dialog_add_domain"), "Enter website domain to blacklist")
        dialog.add_response("cancel", _("cancel"))
        dialog.add_response("add", _("add"))
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        dom_entry = Adw.EntryRow()
        dom_entry.set_title(_("domain"))
        dialog.set_extra_child(dom_entry)

        def on_resp(_d, resp):
            if resp == "add":
                dom = dom_entry.get_text().strip()
                if dom:
                    self.call_dbus("AddDomainRule", dom, "block", cb=lambda _: self.refresh_firewall_rules())

        dialog.connect("response", on_resp)
        dialog.present(self)

    # -------------------------------------------------------------
    # PAGE 4: Bandwidth & Adblocker
    # -------------------------------------------------------------
    def build_page_bandwidth(self):
        scroll = Gtk.ScrolledWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20); box.set_margin_bottom(24); box.set_margin_start(24); box.set_margin_end(24)
        scroll.set_child(box)

        h = Gtk.Label(label=_("bandwidth_title"), xalign=0)
        h.add_css_class("title-2")
        box.append(h)

        # Adblocker Group
        ad_grp = Adw.PreferencesGroup()
        ad_grp.set_title(_("adblocker"))
        ad_grp.set_description(_("adblocker_desc"))

        self.sw_adblock = Adw.SwitchRow()
        self.sw_adblock.set_title("Enable DNS Adblocker")
        self.sw_adblock.connect("notify::active", self.on_adblock_toggled)
        ad_grp.add(self.sw_adblock)

        self.row_ad_count = Adw.ActionRow()
        self.row_ad_count.set_title(_("adblock_count"))
        self.lbl_ad_count = Gtk.Label(label="0 domains")
        self.lbl_ad_count.add_css_class("dim-desc")
        self.row_ad_count.add_suffix(self.lbl_ad_count)

        btn_update_ad = Gtk.Button(label=_("update_adblock"))
        btn_update_ad.connect("clicked", self.on_update_adblock)
        self.row_ad_count.add_suffix(btn_update_ad)
        ad_grp.add(self.row_ad_count)
        box.append(ad_grp)

        # Bandwidth Limits Group
        bw_grp = Adw.PreferencesGroup()
        bw_grp.set_title(_("global_bandwidth"))
        bw_grp.set_description(_("global_bandwidth_desc"))

        self.row_bw_total = Adw.EntryRow()
        self.row_bw_total.set_title("Total Hotspot Speed Limit (kbit/s)")
        self.row_bw_total.set_text("0")
        bw_grp.add(self.row_bw_total)

        save_bw_row = Adw.ActionRow()
        save_bw_btn = Gtk.Button(label=_("save"))
        save_bw_btn.add_css_class("suggested-action")
        save_bw_btn.connect("clicked", self.on_save_global_bw)
        save_bw_row.add_suffix(save_bw_btn)

        rebal_btn = Gtk.Button(label=_("rebalance"))
        rebal_btn.connect("clicked", lambda _: self.call_dbus("RebalanceBandwidth", cb=lambda x: self.toast(f"Rebalanced: {x} kbit/s each")))
        save_bw_row.add_suffix(rebal_btn)
        bw_grp.add(save_bw_row)

        box.append(bw_grp)
        return scroll

    def on_adblock_toggled(self, sw, _param):
        self.call_dbus("SetAdblockEnabled", sw.get_active(), cb=lambda _: self.toast("Adblocker state updated"))

    def on_update_adblock(self, btn):
        btn.set_sensitive(False)
        self.toast("Updating Steven Black adblock list...")
        def done(res):
            btn.set_sensitive(True)
            self.refresh_adblock_status()
            self.toast("Adblock list updated successfully!")
        self.call_dbus("UpdateAdblockList", cb=done)

    def refresh_adblock_status(self):
        def cb(res):
            try:
                st = json.loads(res)
                self.sw_adblock.set_active(st.get("enabled", False))
                cnt = st.get("count", 0)
                self.lbl_ad_count.set_text(f"{cnt:,} active domains")
            except Exception:
                pass
        self.call_dbus("GetAdblockStatus", cb=cb)

    def on_save_global_bw(self, _btn):
        val = self.row_bw_total.get_text().strip()
        self.call_dbus("SetFeatureConfig", "bandwidth", json.dumps({"total_kbit": val}), cb=lambda _: self.toast("Speed limit saved"))

    # -------------------------------------------------------------
    # PAGE 5: Captive Portal
    # -------------------------------------------------------------
    def build_page_portal(self):
        scroll = Gtk.ScrolledWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20); box.set_margin_bottom(24); box.set_margin_start(24); box.set_margin_end(24)
        scroll.set_child(box)

        h = Gtk.Label(label=_("portal_title"), xalign=0)
        h.add_css_class("title-2")
        box.append(h)

        p_grp = Adw.PreferencesGroup()
        p_grp.set_title("Authentication & Landing Page")
        p_grp.set_description(_("portal_desc"))

        # Auth Mode Dropdown
        self.row_portal_auth = Adw.ComboRow()
        self.row_portal_auth.set_title(_("auth_mode"))
        self.row_portal_auth.set_model(Gtk.StringList.new([
            _("auth_open"),
            _("auth_terms"),
            _("auth_user"),
            _("auth_voucher")
        ]))
        p_grp.add(self.row_portal_auth)

        self.row_portal_title = Adw.EntryRow()
        self.row_portal_title.set_title(_("portal_heading"))
        self.row_portal_title.set_text("Welcome to High-Speed Wi-Fi")
        p_grp.add(self.row_portal_title)

        self.row_portal_msg = Adw.EntryRow()
        self.row_portal_msg.set_title(_("portal_message"))
        self.row_portal_msg.set_text("Please sign in or accept terms to access the Internet.")
        p_grp.add(self.row_portal_msg)

        self.row_portal_terms = Adw.EntryRow()
        self.row_portal_terms.set_title(_("portal_terms"))
        self.row_portal_terms.set_text("By continuing you agree to the Terms of Service and Acceptable Use Policy.")
        p_grp.add(self.row_portal_terms)

        self.row_portal_redir = Adw.EntryRow()
        self.row_portal_redir.set_title(_("portal_redirect"))
        self.row_portal_redir.set_text("https://google.com")
        p_grp.add(self.row_portal_redir)

        act_row = Adw.ActionRow()
        save_btn = Gtk.Button(label=_("save_portal"))
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self.on_save_portal)
        act_row.add_suffix(save_btn)

        preview_btn = Gtk.Button(label=_("preview_portal"))
        preview_btn.connect("clicked", lambda _: os.system("xdg-open http://127.0.0.1:8080 &"))
        act_row.add_suffix(preview_btn)
        p_grp.add(act_row)

        box.append(p_grp)
        return scroll

    def on_save_portal(self, _btn):
        t = self.row_portal_title.get_text()
        m = self.row_portal_msg.get_text()
        r = self.row_portal_redir.get_text()
        terms = self.row_portal_terms.get_text()
        self.call_dbus("SetPortalConfig", t, m, r, terms, cb=lambda _: self.toast("Portal configuration saved"))

    # -------------------------------------------------------------
    # PAGE 6: Logs, Port Forwarding & Settings
    # -------------------------------------------------------------
    def build_page_management(self):
        scroll = Gtk.ScrolledWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20); box.set_margin_bottom(24); box.set_margin_start(24); box.set_margin_end(24)
        scroll.set_child(box)

        h = Gtk.Label(label=_("logs_title"), xalign=0)
        h.add_css_class("title-2")
        box.append(h)

        # Visited URLs Section
        url_grp = Adw.PreferencesGroup()
        url_grp.set_title(_("url_logs"))
        url_grp.set_description(_("url_logs_desc"))

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        clr_btn = Gtk.Button(label=_("clear_logs"))
        clr_btn.connect("clicked", lambda _: self.call_dbus("ClearUrlLogs", cb=lambda _: self.refresh_url_logs()))
        btn_box.append(clr_btn)

        exp_btn = Gtk.Button(label=_("export_logs"))
        exp_btn.connect("clicked", self.export_url_logs)
        btn_box.append(exp_btn)
        url_grp.set_header_suffix(btn_box)

        # Log View Area
        self.log_text_view = Gtk.TextView()
        self.log_text_view.set_editable(False)
        self.log_text_view.set_cursor_visible(False)
        self.log_text_view.set_wrap_mode(Gtk.WrapMode.NONE)
        self.log_text_view.add_css_class("log-box")
        self.log_text_view.set_size_request(-1, 180)

        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_size_request(-1, 180)
        log_scroll.set_child(self.log_text_view)
        url_grp.add(log_scroll)
        box.append(url_grp)

        # Port Forwarding Section
        pf_grp = Adw.PreferencesGroup()
        pf_grp.set_title(_("port_forwarding"))
        pf_grp.set_description(_("port_forwarding_desc"))

        add_pf_btn = Gtk.Button(label=_("add_forward"))
        add_pf_btn.add_css_class("suggested-action")
        add_pf_btn.connect("clicked", lambda _: self.show_add_port_forward_dialog())
        pf_grp.set_header_suffix(add_pf_btn)

        self.pf_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        pf_grp.add(self.pf_container)
        box.append(pf_grp)

        # Diagnostics & Maintenance
        sys_grp = Adw.PreferencesGroup()
        sys_grp.set_title("System Maintenance")

        diag_row = Adw.ActionRow()
        diag_row.set_title(_("diagnostics"))
        diag_btn = Gtk.Button(label="Run Diagnostics")
        diag_btn.connect("clicked", self.run_diagnostics)
        diag_row.add_suffix(diag_btn)
        sys_grp.add(diag_row)

        bk_row = Adw.ActionRow()
        bk_row.set_title(_("backup_db"))
        bk_btn = Gtk.Button(label="Create Backup")
        bk_btn.connect("clicked", lambda _: self.call_dbus("BackupDatabase", cb=lambda dest: self.toast(f"Backup created: {dest}")))
        bk_row.add_suffix(bk_btn)
        sys_grp.add(bk_row)

        box.append(sys_grp)
        return scroll

    def refresh_url_logs(self):
        self.call_dbus("GetUrlLog", 200, cb=self.on_url_logs_data)

    def on_url_logs_data(self, res):
        try:
            logs = json.loads(res)
        except Exception:
            logs = []
        self.url_logs_data = logs
        buf = self.log_text_view.get_buffer()
        lines = []
        for item in reversed(logs):
            t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item.get("ts", 0)))
            ip = item.get("ip") or "10.42.0.x"
            url = item.get("url", "")
            lines.append(f"[{t_str}]  {ip:15}  ->  {url}")
        buf.set_text("\n".join(lines) if lines else "No visited URLs logged yet.")

    def export_url_logs(self, _btn):
        home_down = Path.home() / "Downloads"
        home_down.mkdir(exist_ok=True)
        out_file = home_down / f"lhm-url-log-{int(time.time())}.txt"
        lines = []
        for item in reversed(self.url_logs_data):
            t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item.get("ts", 0)))
            ip = item.get("ip") or "10.42.0.x"
            url = item.get("url", "")
            lines.append(f"[{t_str}]  {ip:15}  ->  {url}")
        out_file.write_text("\n".join(lines), encoding="utf-8")
        self.toast(f"Exported to {out_file.name}")

    def refresh_port_forwards(self):
        self.call_dbus("ListPortForwards", cb=self.on_port_forwards_data)

    def on_port_forwards_data(self, res):
        try:
            pfs = json.loads(res)
        except Exception:
            pfs = []
        while child := self.pf_container.get_first_child():
            self.pf_container.remove(child)

        for p in pfs:
            row = Adw.ActionRow()
            row.set_title(f"Port {p['listen_port']} ({p['proto'].upper()}) -> {p['destination_ip']}:{p['destination_port']}")
            del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
            del_btn.add_css_class("flat")
            del_btn.add_css_class("destructive-action")
            del_btn.connect("clicked", lambda _, proto=p["proto"], port=p["listen_port"]: self.call_dbus("DeletePortForward", proto, port, cb=lambda _: self.refresh_port_forwards()))
            row.add_suffix(del_btn)
            self.pf_container.append(row)

    def show_add_port_forward_dialog(self):
        dialog = Adw.AlertDialog.new(_("dialog_add_forward"), "Forward an external port to an internal device")
        dialog.add_response("cancel", _("cancel"))
        dialog.add_response("add", _("add"))
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(10); box.set_margin_bottom(10)

        proto_combo = Adw.ComboRow()
        proto_combo.set_title(_("protocol"))
        proto_combo.set_model(Gtk.StringList.new(["TCP", "UDP"]))
        box.append(proto_combo)

        listen_entry = Adw.EntryRow()
        listen_entry.set_title("Listen Port")
        box.append(listen_entry)

        dst_ip_entry = Adw.EntryRow()
        dst_ip_entry.set_title(_("destination_ip"))
        dst_ip_entry.set_text("10.42.0.10")
        box.append(dst_ip_entry)

        dst_port_entry = Adw.EntryRow()
        dst_port_entry.set_title(_("destination_port"))
        box.append(dst_port_entry)

        dialog.set_extra_child(box)

        def on_resp(_d, resp):
            if resp == "add":
                proto = "tcp" if proto_combo.get_selected() == 0 else "udp"
                listen = listen_entry.get_text().strip()
                dst_ip = dst_ip_entry.get_text().strip()
                dst_port = dst_port_entry.get_text().strip()
                if listen.isdigit() and dst_port.isdigit() and dst_ip:
                    self.call_dbus("AddPortForward", proto, int(listen), dst_ip, int(dst_port), cb=lambda _: self.refresh_port_forwards())
                else:
                    self.toast("Invalid port or IP")

        dialog.connect("response", on_resp)
        dialog.present(self)

    def run_diagnostics(self, _btn):
        def cb(res):
            try:
                diag = json.loads(res)
                text = f"NetworkManager: {'OK' if diag.get('nmcli') else 'FAILED'}\n" \
                       f"nftables: {'OK' if diag.get('nft') else 'FAILED'}\n" \
                       f"dnsmasq: {'OK' if diag.get('dnsmasq') else 'FAILED'}\n" \
                       f"IP Forwarding: {diag.get('ip_forward')}"
                alert = Adw.AlertDialog.new("System Diagnostics", text)
                alert.add_response("close", _("close"))
                alert.present(self)
            except Exception as e:
                self.toast(f"Error: {e}")
        self.call_dbus("Diagnostics", cb=cb)

    # -------------------------------------------------------------
    # Polling & Startup
    # -------------------------------------------------------------
    def initial_load(self):
        # List devices
        self.call_dbus("ListInterfaces", cb=self.on_interfaces_loaded)
        # Status
        self.call_dbus("GetStatus", cb=self.on_status_loaded)
        # Initial refresh
        self.refresh_firewall_rules()
        self.refresh_adblock_status()
        self.refresh_port_forwards()
        self.refresh_url_logs()

    def on_interfaces_loaded(self, res):
        try:
            devs = json.loads(res)
        except Exception:
            devs = []
        self.detected_devices = devs

        inet_items = ["Automatic (Default Route)"]
        wifi_items = []
        for d in devs:
            dev_name = d.get("device", "")
            dev_type = d.get("type", "")
            inet_items.append(f"{dev_name} ({dev_type})")
            if dev_type == "wifi":
                wifi_items.append(dev_name)

        self.inet_model.splice(0, self.inet_model.get_n_items(), inet_items)
        if wifi_items:
            self.adapter_model.splice(0, self.adapter_model.get_n_items(), wifi_items)
            self.active_iface = wifi_items[0]

    def on_status_loaded(self, res):
        try:
            st = json.loads(res)
            self.hotspot_running = st.get("hotspot") == "running"
            if st.get("interface"):
                self.active_iface = st["interface"]
            self.update_status_ui()
        except Exception:
            pass

    def poll_status(self):
        """Background status and traffic poll every 3 seconds."""
        self.refresh_clients()
        self.refresh_url_logs()
        return True # Keep running timer

class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=SERVICE)

    def do_activate(self):
        win = MainWindow(self)
        win.present()

if __name__ == "__main__":
    App().run(sys.argv)
