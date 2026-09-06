Name: linux-hotspot-manager
Version: 2.0.0
Release: 1%{?dist}
Summary: Open-source Linux hotspot manager
License: GPL-3.0-or-later
BuildArch: noarch
Requires: python3, python3-gobject, python3-dbus-next, gtk4, libadwaita, NetworkManager, nftables, dnsmasq, iproute, polkit, systemd

%description
GTK4/libadwaita hotspot manager with a privileged D-Bus host service.

%install
install -Dpm0755 src/main.py %{buildroot}%{_bindir}/linux-hotspot-manager
install -Dpm0755 host/linux-hotspot-manager-service.py %{buildroot}%{_prefix}/lib/linux-hotspot-manager/linux-hotspot-manager-service.py
install -Dpm0755 portal/server.py %{buildroot}%{_prefix}/lib/linux-hotspot-manager/portal-server.py
install -Dpm0644 host/com.shazid.LinuxHotspotManager.service %{buildroot}%{_datadir}/dbus-1/system-services/com.shazid.LinuxHotspotManager.service
install -Dpm0644 polkit/com.shazid.LinuxHotspotManager.policy %{buildroot}%{_datadir}/polkit-1/actions/com.shazid.LinuxHotspotManager.policy
install -Dpm0644 systemd/linux-hotspot-manager.service %{buildroot}%{_unitdir}/linux-hotspot-manager.service
install -Dpm0644 systemd/linux-hotspot-manager-portal.service %{buildroot}%{_unitdir}/linux-hotspot-manager-portal.service
install -Dpm0644 data/com.shazid.LinuxHotspotManager.desktop %{buildroot}%{_datadir}/applications/com.shazid.LinuxHotspotManager.desktop
install -Dpm0644 data/com.shazid.LinuxHotspotManager.metainfo.xml %{buildroot}%{_datadir}/metainfo/com.shazid.LinuxHotspotManager.metainfo.xml
install -Dpm0644 data/icon.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/com.shazid.LinuxHotspotManager.svg
install -Dpm0644 LICENSE %{buildroot}%{_licensedir}/%{name}/LICENSE

%post
%systemd_post linux-hotspot-manager.service
%systemd_post linux-hotspot-manager-portal.service

%preun
%systemd_preun linux-hotspot-manager.service
%systemd_preun linux-hotspot-manager-portal.service

%postun
%systemd_postun_with_restart linux-hotspot-manager.service
%systemd_postun_with_restart linux-hotspot-manager-portal.service

%files
%license %{_licensedir}/%{name}/LICENSE
%{_bindir}/linux-hotspot-manager
%{_prefix}/lib/linux-hotspot-manager/
%{_datadir}/dbus-1/system-services/com.shazid.LinuxHotspotManager.service
%{_datadir}/polkit-1/actions/com.shazid.LinuxHotspotManager.policy
%{_unitdir}/linux-hotspot-manager.service
%{_unitdir}/linux-hotspot-manager-portal.service
%{_datadir}/applications/com.shazid.LinuxHotspotManager.desktop
%{_datadir}/metainfo/com.shazid.LinuxHotspotManager.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/com.shazid.LinuxHotspotManager.svg
