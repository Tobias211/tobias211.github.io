#!/usr/bin/env python3
"""Check device availability and email when a device is unavailable."""

import csv
import re
import socket
import subprocess
import smtplib
import time
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from netmiko import ConnectHandler

CSV_FILE = Path(__file__).parent / "network_devices.csv"
SMTP_HOST = "10.10.10.100"
SMTP_PORT = 25


def ping(ip):
    result = subprocess.run(
        ["ping", "-c", "1", "-W", "2", ip],
        capture_output=True,
    )
    return result.returncode == 0


def console_up(port):
    try:
        socket.create_connection(("127.0.0.1", port), timeout=2).close()
        return True
    except OSError:
        return False


def get_dhcp_ip(port, user, password):
    conn = ConnectHandler(
        device_type="generic_termserver_telnet",
        host="127.0.0.1",
        port=port,
        username=user,
        password=password,
        default_enter="\r\n",
    )
    time.sleep(2)
    conn.write_channel("\r\n")
    time.sleep(1)
    conn.write_channel(user + "\r\n")
    time.sleep(1)
    conn.write_channel(password + "\r\n")
    time.sleep(2)
    conn.write_channel("hostname -I\r\n")
    time.sleep(2)
    output = conn.read_channel()
    conn.disconnect()
    match = re.search(r"(\d+\.\d+\.\d+\.\d+)", output)
    return match.group(1) if match else "Unknown"


def send_unavailable_email(name, ip, timestamp):
    body = f"""Dear Network Administrator,

This is an automated notification that the following network device is currently unavailable:

Device Name: {name}
IP Address: {ip}
Last Checked: {timestamp}

Please investigate this issue at your earliest convenience.

Best regards,
Network Monitoring System
"""
    msg = EmailMessage()
    msg["Subject"] = f"Network Device Unavailable: {name} ({ip})"
    msg["From"] = "monitor@network.local"
    msg["To"] = "admin@network.local"
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as conn:
        conn.send_message(msg)


timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

with open(CSV_FILE) as f:
    for row in csv.DictReader(f):
        name = row["Device Name"]
        addr = row["Device Address"].strip()
        port = int(row["Access Port"])
        user = row["Username"].strip()
        password = row["Password"].strip()
        os_type = row["OS"].strip()

        if addr == "None" or os_type == "OpenvSwitch":t
            ip = "N/A"
            available = console_up(port)
        elif addr == "DHCP":
            try:
                ip = get_dhcp_ip(port, user, password)
                available = ping(ip) if ip != "Unknown" else False
            except Exception:
                ip = "Unknown"
                available = False
        else:
            ip = addr
            available = ping(ip)

        status = "UP" if available else "DOWN"
        print(f"{name} ({ip}): {status}")

        if not available:
            try:
                send_unavailable_email(name, ip, timestamp)
                print(f"  Email sent for {name}")
            except (TimeoutError, OSError) as e:
                print(f"  Email failed for {name}: {e}")
