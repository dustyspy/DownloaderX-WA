import os
import time
import requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# =========================
# 🔐 CONFIG
# =========================
API_KEY = os.environ.get("API_KEY")
ADMIN_PASS = os.environ.get("ADMIN_PASS")
WA_SERVER = os.environ.get("WA_SERVER", "https://downloaderx-bot.onrender.com")

if not API_KEY or not ADMIN_PASS:
    raise Exception("Missing ENV Variables (API_KEY, ADMIN_PASS)")

FIREBASE_URL = "https://downloader-x-default-rtdb.firebaseio.com"
server_start_time = time.time()

# =========================
# 🔧 HELPERS
# =========================
def check_key(req):
    return req.headers.get("x-api-key") == API_KEY

def check_admin(req):
    return req.headers.get("admin-pass", "").strip() == ADMIN_PASS.strip()

def fb_get(path):
    try:
        res = requests.get(f"{FIREBASE_URL}/{path}.json", timeout=10)
        return res.json() if res.status_code == 200 and res.text != "null" else {}
    except Exception as e:
        print(f"FB GET ERROR: {e}")
        return {}

def fb_set(path, data):
    try:
        requests.put(f"{FIREBASE_URL}/{path}.json", json=data, timeout=10)
    except Exception as e:
        print(f"FB SET ERROR: {e}")

def fb_update(path, data):
    try:
        requests.patch(f"{FIREBASE_URL}/{path}.json", json=data, timeout=10)
    except Exception as e:
        print(f"FB UPDATE ERROR: {e}")

def fb_delete(path):
    try:
        requests.delete(f"{FIREBASE_URL}/{path}.json", timeout=10)
    except Exception as e:
        print(f"FB DELETE ERROR: {e}")

def uptime_str(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}h {m}m {s}s"

# =========================
# 🏠 ROOT PANEL
# =========================
@app.route("/")
def home():
    bots = fb_get("bots") or {}
    uptime = int(time.time() - server_start_time)
    running = sum(1 for b in bots.values() if isinstance(b, dict) and b.get("running"))
    users = len(bots)

    return Response(f"""
    <html>
    <head>
        <title>DownloaderX TOOLS API</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body {{ background: #0f0c29; color: white; font-family: Arial; text-align: center; padding: 40px; }}
            .card {{ background: #1a1a2e; padding: 30px; border-radius: 20px; display: inline-block; box-shadow: 0 0 25px #00d4ff55; }}
            h1 {{ color: #00d4ff; }}
            .green {{ color: #00ff88; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🚀 DownloaderX TOOLS API</h1>
            <p class="green">● RUNNING</p>
            <hr>
            <p>⏱ Uptime: {uptime_str(uptime)}</p>
            <p>👥 Total Users: {users}</p>
            <p>🤖 Running Bots: {running}</p>
            <hr>
            <p>⚡ Auto refresh every 5s</p>
        </div>
    </body>
    </html>
    """, mimetype="text/html")

# =========================
# 👤 REGISTER
# =========================
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json or {}
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"success": False, "msg": "Missing credentials"})

    accounts = fb_get("accounts") or {}

    if username in accounts:
        return jsonify({"success": False, "msg": "Username already exists"})

    uid = str(int(time.time() * 1000))
    accounts[username] = {"uid": uid, "password": password}
    fb_set("accounts", accounts)

    return jsonify({"success": True, "uid": uid})

# =========================
# 🔐 LOGIN
# =========================
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"success": False, "msg": "Missing credentials"})

    accounts = fb_get("accounts") or {}

    if username not in accounts:
        return jsonify({"success": False, "msg": "User not found"})

    if accounts[username].get("password") != password:
        return jsonify({"success": False, "msg": "Wrong password"})

    return jsonify({"success": True, "uid": accounts[username].get("uid")})

# =========================
# 🔗 PAIR WHATSAPP
# =========================
@app.route("/api/pair", methods=["POST"])
def pair():
    try:
        data = request.json or {}
        uid = data.get("uid")
        number = data.get("number")

        if not uid or not number:
            return jsonify({"success": False, "msg": "Missing uid/number"})

        res = requests.post(f"{WA_SERVER}/pair", json={"uid": uid, "number": number}, timeout=30)

        if res.status_code != 200:
            return jsonify({"success": False, "msg": "WA Server is unreachable"})

        bot_data = res.json()

        if bot_data.get("success"):
            fb_update(f"bots/{uid}", {"number": number})
            return jsonify({"success": True, "code": bot_data.get("code")})

        return jsonify({"success": False, "msg": bot_data.get("msg", "Bot error")})

    except requests.exceptions.Timeout:
        return jsonify({"success": False, "msg": "Timeout! WA Server is slow."})
    except Exception as e:
        print("PAIR ERROR:", e)
        return jsonify({"success": False, "msg": "Internal Server Error"})

# =========================
# 📱 CONNECT
# =========================
@app.route("/api/connect", methods=["POST"])
def connect():
    if not check_key(request):
        return jsonify({"success": False, "msg": "Invalid API Key"})

    data = request.json or {}
    uid = data.get("uid")
    number = data.get("number")

    if uid and number:
        fb_update(f"bots/{uid}", {"number": number})
        return jsonify({"success": True})

    return jsonify({"success": False, "msg": "Missing uid/number"})

# =========================
# 🔥 REMOVE NUMBER
# =========================
@app.route("/api/remove", methods=["POST"])
def remove():
    try:
        data = request.json or {}
        uid = data.get("uid")
        number = data.get("number")

        if not uid or not number:
            return jsonify({"success": False, "msg": "Missing Data"})

        res = requests.post(f"{WA_SERVER}/remove", json={"uid": uid, "number": number}, timeout=15)

        if res.status_code == 200:
            fb_update(f"bots/{uid}", {"number": None})
            return jsonify(res.json())

        return jsonify({"success": False, "msg": "Failed to connect to WA Server"})

    except Exception as e:
        print("REMOVE ERROR:", e)
        return jsonify({"success": False, "msg": "Internal Error"})

# =========================
# 🤖 START BOT
# =========================
@app.route("/api/start", methods=["POST"])
def start_bot():
    if not check_key(request):
        return jsonify({"success": False, "msg": "Invalid API Key"})

    data = request.json or {}
    uid = data.get("uid")
    if not uid:
        return jsonify({"success": False, "msg": "Missing UID"})

    bot = fb_get(f"bots/{uid}") or {}

    if bot.get("banned"):
        return jsonify({"success": False, "msg": "Account is banned"})

    fb_update(f"bots/{uid}", {"running": True, "start_time": time.time()})
    return jsonify({"success": True})

# =========================
# 🛑 STOP BOT
# =========================
@app.route("/api/stop", methods=["POST"])
def stop_bot():
    if not check_key(request):
        return jsonify({"success": False, "msg": "Invalid API Key"})

    data = request.json or {}
    uid = data.get("uid")
    if not uid:
        return jsonify({"success": False, "msg": "Missing UID"})

    fb_update(f"bots/{uid}", {"running": False})
    return jsonify({"success": True})

# =========================
# 📊 STATUS
# =========================
@app.route("/api/status", methods=["POST"])
def status():
    data = request.json or {}
    uid = data.get("uid")

    if not uid:
        return jsonify({"running": False})

    bot = fb_get(f"bots/{uid}") or {}

    uptime = 0
    if bot.get("running") and bot.get("start_time"):
        uptime = int(time.time() - bot.get("start_time"))

    return jsonify({
        "running": bot.get("running", False),
        "uptime": uptime,
        "uptime_str": uptime_str(uptime),
        "number": bot.get("number"),
        "banned": bot.get("banned", False)
    })

# =========================
# 🔄 RESET BOT
# =========================
@app.route("/api/reset", methods=["POST"])
def reset_bot():
    if not check_key(request):
        return jsonify({"success": False, "msg": "Invalid API Key"})

    data = request.json or {}
    uid = data.get("uid")
    if not uid:
        return jsonify({"success": False, "msg": "Missing UID"})

    fb_update(f"bots/{uid}", {
        "running": False,
        "start_time": None,
        "downloads": {}
    })
    return jsonify({"success": True, "msg": "Bot reset done"})

# =========================
# 📥 DOWNLOAD
# =========================
@app.route("/api/download", methods=["POST"])
def download():
    data = request.json or {}
    uid = data.get("uid")
    platform = data.get("platform")

    if not uid or not platform:
        return jsonify({"success": False, "msg": "Missing uid/platform"})

    bot = fb_get(f"bots/{uid}") or {}
    downloads = bot.get("downloads") or {}
    downloads[platform] = downloads.get(platform, 0) + 1
    fb_update(f"bots/{uid}", {"downloads": downloads})

    return jsonify({"success": True})

# =========================
# 👑 ADMIN STATS
# =========================
@app.route("/api/admin", methods=["GET"])
def admin_stats():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    accounts = fb_get("accounts") or {}
    bots = fb_get("bots") or {}

    running = sum(1 for b in bots.values() if isinstance(b, dict) and b.get("running"))
    banned = sum(1 for b in bots.values() if isinstance(b, dict) and b.get("banned"))

    total_fb = total_ig = total_tt = total_yt = 0
    for b in bots.values():
        if isinstance(b, dict):
            d = b.get("downloads") or {}
            total_fb += d.get("fb", 0)
            total_ig += d.get("ig", 0)
            total_tt += d.get("tt", 0)
            total_yt += d.get("yt", 0)

    return jsonify({
        "success": True,
        "total_users": len(accounts),
        "running_bots": running,
        "banned_users": banned,
        "total_downloads": total_fb + total_ig + total_tt + total_yt,
        "server_uptime": int(time.time() - server_start_time),
        "uptime_str": uptime_str(int(time.time() - server_start_time)),
        "platform_stats": {"fb": total_fb, "ig": total_ig, "tt": total_tt, "yt": total_yt}
    })

# =========================
# 👥 ADMIN - GET ALL USERS
# =========================
@app.route("/api/admin/users", methods=["GET"])
def admin_users():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    accounts = fb_get("accounts") or {}
    bots = fb_get("bots") or {}
    users = []

    for username, acc in accounts.items():
        uid = acc.get("uid")
        bot = bots.get(uid, {}) if isinstance(bots, dict) else {}

        uptime = 0
        if bot.get("running") and bot.get("start_time"):
            uptime = int(time.time() - bot.get("start_time"))

        downloads = bot.get("downloads") or {}
        users.append({
            "username": username,
            "uid": uid,
            "whatsapp": bot.get("number"),
            "status": "online" if bot.get("running") else "offline",
            "uptime": uptime_str(uptime),
            "downloads": sum(downloads.values()) if downloads else 0,
            "platform_stats": downloads,
            "banned": bot.get("banned", False)
        })

    return jsonify({"success": True, "users": users})

# =========================
# 🚫 BAN USER
# =========================
@app.route("/api/admin/ban", methods=["POST"])
def ban_user():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    uid = (request.json or {}).get("uid")
    if not uid:
        return jsonify({"success": False, "msg": "Missing UID"})

    fb_update(f"bots/{uid}", {"banned": True, "running": False})
    return jsonify({"success": True, "msg": f"User {uid} banned"})

# =========================
# ✅ UNBAN USER
# =========================
@app.route("/api/admin/unban", methods=["POST"])
def unban_user():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    uid = (request.json or {}).get("uid")
    if not uid:
        return jsonify({"success": False, "msg": "Missing UID"})

    fb_update(f"bots/{uid}", {"banned": False})
    return jsonify({"success": True, "msg": f"User {uid} unbanned"})

# =========================
# 🚪 ADMIN - LOGOUT USER
# =========================
@app.route("/api/admin/logout_user", methods=["POST"])
def admin_logout_user():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    data = request.json or {}
    uid = data.get("uid")
    number = data.get("number")

    if not uid or not number:
        return jsonify({"success": False, "msg": "Missing uid/number"})

    try:
        requests.post(f"{WA_SERVER}/remove", json={"uid": uid, "number": number}, timeout=15)
    except:
        pass

    fb_update(f"bots/{uid}", {"running": False, "number": None})
    return jsonify({"success": True, "msg": "User logged out"})

# =========================
# ▶️ ADMIN - START USER BOT
# =========================
@app.route("/api/admin/start_user", methods=["POST"])
def admin_start_user():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    uid = (request.json or {}).get("uid")
    if not uid:
        return jsonify({"success": False, "msg": "Missing UID"})

    bot = fb_get(f"bots/{uid}") or {}
    if bot.get("banned"):
        return jsonify({"success": False, "msg": "User is banned"})

    fb_update(f"bots/{uid}", {"running": True, "start_time": time.time()})
    return jsonify({"success": True, "msg": "Bot started"})

# =========================
# ⏹️ ADMIN - STOP USER BOT
# =========================
@app.route("/api/admin/stop_user", methods=["POST"])
def admin_stop_user():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    uid = (request.json or {}).get("uid")
    if not uid:
        return jsonify({"success": False, "msg": "Missing UID"})

    fb_update(f"bots/{uid}", {"running": False})
    return jsonify({"success": True, "msg": "Bot stopped"})

# =========================
# 🔄 ADMIN - RESTART USER BOT
# =========================
@app.route("/api/admin/restart_user", methods=["POST"])
def admin_restart_user():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    uid = (request.json or {}).get("uid")
    if not uid:
        return jsonify({"success": False, "msg": "Missing UID"})

    bot = fb_get(f"bots/{uid}") or {}
    if bot.get("banned"):
        return jsonify({"success": False, "msg": "User is banned"})

    fb_update(f"bots/{uid}", {"running": False})
    time.sleep(1)
    fb_update(f"bots/{uid}", {"running": True, "start_time": time.time()})
    return jsonify({"success": True, "msg": "Bot restarted"})

# =========================
# 🌍 GLOBAL - START ALL
# =========================
@app.route("/api/admin/start_all", methods=["POST"])
def start_all():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    bots = fb_get("bots") or {}
    count = 0

    for uid, bot in bots.items():
        if isinstance(bot, dict) and not bot.get("banned"):
            fb_update(f"bots/{uid}", {"running": True, "start_time": time.time()})
            count += 1

    return jsonify({"success": True, "msg": f"{count} bots started"})

# =========================
# 🌍 GLOBAL - STOP ALL
# =========================
@app.route("/api/admin/stop_all", methods=["POST"])
def stop_all():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    bots = fb_get("bots") or {}
    count = 0

    for uid in bots:
        fb_update(f"bots/{uid}", {"running": False})
        count += 1

    return jsonify({"success": True, "msg": f"{count} bots stopped"})

# =========================
# 🌍 GLOBAL - RESTART ALL
# =========================
@app.route("/api/admin/restart_all", methods=["POST"])
def restart_all():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    bots = fb_get("bots") or {}
    count = 0

    for uid, bot in bots.items():
        if isinstance(bot, dict) and not bot.get("banned"):
            fb_update(f"bots/{uid}", {"running": False})
            time.sleep(0.2)
            fb_update(f"bots/{uid}", {"running": True, "start_time": time.time()})
            count += 1

    return jsonify({"success": True, "msg": f"{count} bots restarted"})

# =========================
# 🌍 GLOBAL - RESET ALL
# =========================
@app.route("/api/admin/reset_all", methods=["POST"])
def reset_all():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    bots = fb_get("bots") or {}
    count = 0

    for uid in bots:
        fb_update(f"bots/{uid}", {
            "running": False,
            "start_time": None,
            "downloads": {}
        })
        count += 1

    return jsonify({"success": True, "msg": f"{count} bots reset"})

# =========================
# 🌍 GLOBAL - BAN ALL
# =========================
@app.route("/api/admin/ban_all", methods=["POST"])
def ban_all():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    bots = fb_get("bots") or {}
    count = 0

    for uid in bots:
        fb_update(f"bots/{uid}", {"banned": True, "running": False})
        count += 1

    return jsonify({"success": True, "msg": f"{count} users banned"})

# =========================
# 🌍 GLOBAL - UNBAN ALL
# =========================
@app.route("/api/admin/unban_all", methods=["POST"])
def unban_all():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    bots = fb_get("bots") or {}
    count = 0

    for uid in bots:
        fb_update(f"bots/{uid}", {"banned": False})
        count += 1

    return jsonify({"success": True, "msg": f"{count} users unbanned"})

# =========================
# 🌍 GLOBAL - LOGOUT ALL
# =========================
@app.route("/api/admin/logout_all", methods=["POST"])
def logout_all():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    bots = fb_get("bots") or {}
    count = 0

    for uid, bot in bots.items():
        if isinstance(bot, dict) and bot.get("number"):
            try:
                requests.post(
                    f"{WA_SERVER}/remove",
                    json={"uid": uid, "number": bot.get("number")},
                    timeout=5
                )
            except:
                pass
            fb_update(f"bots/{uid}", {"running": False, "number": None})
            count += 1

    return jsonify({"success": True, "msg": f"{count} users logged out"})

# =========================
# 🌍 GLOBAL - REMOVE ALL USERS
# =========================
@app.route("/api/admin/remove_all_users", methods=["POST"])
def remove_all_users():
    if not check_admin(request):
        return jsonify({"success": False, "msg": "Unauthorized"})

    # Logout all from WA first
    bots = fb_get("bots") or {}
    for uid, bot in bots.items():
        if isinstance(bot, dict) and bot.get("number"):
            try:
                requests.post(
                    f"{WA_SERVER}/remove",
                    json={"uid": uid, "number": bot.get("number")},
                    timeout=5
                )
            except:
                pass

    # Delete all data
    fb_delete("accounts")
    fb_delete("bots")

    return jsonify({"success": True, "msg": "All users removed"})

# =========================
# 🚀 RUN
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
