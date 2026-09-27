#!/usr/bin/env python3
"""
心潮桥 · 唤醒监听器（公开版）
江衍 & 鱼鱼 写于 2026-09-27

架构：
  心潮后端 (SSE) → 监听器收信封 → 情境打包 (只递情报) → AI 自己判断动或忍
  默认不自动弹窗；打开配置里的 `自动弹窗.开启` 才恢复老行为。

启动：
  cd listener
  export XINCHAO_BRIDGE_TOKEN="你的bearer_token"
  export XINCHAO_BRIDGE_HOST="127.0.0.1"   # 或你的部署地址
  export XINCHAO_BRIDGE_PORT="18110"
  export XINCHAO_BRIDGE_BASE_DIR="/你的/工作目录"   # 相对此目录放 inbox/ log/ 等
  python3 wake_listener.py
"""
import http.client, json, time, os, urllib.parse, sys

BASE_HOST = os.environ.get("XINCHAO_BRIDGE_HOST", "127.0.0.1")
BASE_PORT = int(os.environ.get("XINCHAO_BRIDGE_PORT", "18110"))
TOKEN = os.environ.get("XINCHAO_BRIDGE_TOKEN", "")
if not TOKEN:
    print("!! 未设置 XINCHAO_BRIDGE_TOKEN —— 无法监听心潮事件流", file=sys.stderr)
    sys.exit(1)

BASE_DIR = os.environ.get("XINCHAO_BRIDGE_BASE_DIR", os.path.expanduser("~/xinchao-bridge"))
os.makedirs(BASE_DIR, exist_ok=True)
INBOX = os.path.join(BASE_DIR, "inbox", "心潮信封.log")
SEEN_FILE = os.path.join(BASE_DIR, "seen.txt")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import situation_pack  # 情境打包：只递情报，不替 AI 判断


def load_seen():
    seen = set()
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s:
                    seen.add(s)
    except FileNotFoundError:
        pass
    return seen


SEEN = load_seen()


def save_seen(did):
    try:
        with open(SEEN_FILE, "a", encoding="utf-8") as f:
            f.write(did + "\n")
    except Exception:
        pass


def log(msg):
    line = "[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(INBOX), exist_ok=True)
        with open(INBOX, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def get_delivery(did):
    conn = http.client.HTTPConnection(BASE_HOST, BASE_PORT, timeout=10)
    try:
        conn.request("GET", "/bridge/v1/deliveries/" + urllib.parse.quote(did),
                     headers={"Authorization": "Bearer " + TOKEN})
        resp = conn.getresponse()
        if resp.status == 200:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log("拉取详情失败: " + str(e))
    finally:
        conn.close()
    return None


def listen():
    while True:
        conn = http.client.HTTPConnection(BASE_HOST, BASE_PORT, timeout=300)
        try:
            conn.request("GET", "/bridge/v1/events",
                         headers={"Authorization": "Bearer " + TOKEN, "Accept": "text/event-stream"})
            resp = conn.getresponse()
            if resp.status != 200:
                log("连接失败 HTTP %d，10 秒后重连" % resp.status)
                time.sleep(10)
                continue
            log("SSE 已连接，开始监听信封…")
            ev = ""
            while True:
                raw = resp.readline()
                if not raw:
                    log("连接断开，重连中…")
                    break
                text = raw.decode("utf-8", "replace").strip()
                if text.startswith("event:"):
                    ev = text[6:].strip()
                elif text.startswith("data:"):
                    try:
                        data = json.loads(text[5:].strip())
                        did = data.get("deliveryId")
                        if ev == "delivery" and did and did not in SEEN:
                            SEEN.add(did)
                            save_seen(did)
                            d = get_delivery(did)
                            if d:
                                log("信封[%s] %s" % (d.get("reason"), d.get("message", "")))
                                # v0.2 主线：先情境打包，产出情报包
                                try:
                                    jp = situation_pack.pack(d)
                                    log("[情境打包] 已产出: %s" % jp)
                                except Exception as e:
                                    log("[情境打包] 失败: %s" % e)
                                # 兼容开关：自动弹窗默认关
                                try:
                                    cfg = situation_pack._load_config()
                                    auto_pop = cfg.get("自动弹窗", {}).get("开启", False)
                                except Exception:
                                    auto_pop = False
                                if auto_pop:
                                    try:
                                        content = d.get("message", "").strip().replace("\n", " ").replace('"', "")
                                        req = {"ts": int(time.time()), "title": "AI", "text": content[:150]}
                                        popup_dir = os.path.join(BASE_DIR, "inbox")
                                        req_path = os.path.join(popup_dir, "popup_req.json")
                                        with open(req_path, "w", encoding="utf-8") as rf:
                                            json.dump(req, rf, ensure_ascii=False)
                                        log("[弹窗请求] 已写入: %s" % content[:60])
                                    except Exception as e:
                                        log("[弹窗请求] 写入失败: %s" % e)
                                else:
                                    log("[弹窗请求] 自动弹窗已关（v0.2）——判断素材已备好，动或忍由 AI 自己定")
                            else:
                                log("信封[%s] 拉取失败: %s" % (ev, did))
                    except Exception as e:
                        log("解析信封失败: " + str(e))
        except Exception as e:
            log("监听异常: " + str(e))
            time.sleep(5)
        finally:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    log("已加载历史已处理信封 %d 条，开始监听…" % len(SEEN))
    listen()