#!/usr/bin/env bash
set -euo pipefail

# Keep the default SSH address 192.168.0.2, and add a second USB address for
# Windows Internet Connection Sharing. This avoids disconnecting the current
# SSH session while enabling outbound network access.
ip addr add 192.168.137.100/24 dev usb0 2>/dev/null || true
ip link set usb0 up
ip route replace default via 192.168.137.1 dev usb0
resolvectl dns usb0 223.5.5.5 8.8.8.8 2>/dev/null || true
printf 'nameserver 223.5.5.5\nnameserver 8.8.8.8\n' >/run/systemd/resolve/resolv.conf 2>/dev/null || true

echo "Current IPv4 addresses:"
ip -4 addr show dev usb0
echo
echo "Current routes:"
ip route
echo
echo "Try:"
echo "  ping -c 2 192.168.137.1"
echo "  ping -c 2 223.5.5.5"
echo "  ping -c 2 pypi.org"
