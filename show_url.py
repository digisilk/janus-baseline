#!/usr/bin/env python3
"""
Show correct URL to access Janus
"""

import socket
import subprocess

print("="*60)
print("JANUS ACCESS INFO")
print("="*60)

# Get IP address
try:
    # Get hostname
    hostname = socket.gethostname()
    # Get IP
    ip = socket.gethostbyname(hostname)
    
    print(f"\nYour server IP: {ip}")
    print(f"\nAccess Janus at:")
    print(f"  http://{ip}:8050")
    print(f"\nNOT http://127.0.0.1:8050")
except:
    print("\nCouldn't detect IP automatically")
    print("Run: hostname -I")
    print("Then access: http://<that-ip>:8050")

print("\n" + "="*60)

# Also try hostname -I
try:
    result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
    if result.stdout:
        ips = result.stdout.strip().split()
        print(f"\nAll IPs: {', '.join(ips)}")
        print(f"Try: http://{ips[0]}:8050")
except:
    pass
