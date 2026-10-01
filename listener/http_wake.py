#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
心潮桥 · 外部唤醒模块（公开版）
江衍 & 鱼鱼 写于 2026-09-29

为什么需要它：
  监听器收到了心潮的信封（情绪信号），但"叫醒 AI"这一步，
  不同宿主有不同正门。这个模块针对 Operit 的 external-chat API，
  把唤醒素材递进 AI 的对话流——不靠定时工作流，靠情绪本身触发。

两种投递模式：
  v0.3 冒泡路：走宿主 external-chat 正门直发，唤醒消息会冒到聊天流。
  v0.4 静默优先（默认）：唤醒素材先塞进心潮黑匣子（xinchao_box.put,
  surface=true）——人类看不到，下一轮对话注入时 AI 自己看到再决定。
  命中强信号关键词时才回退到 external-chat 正门冒泡。

双保险：无论如何先塞匣子兜底（不丢信号），再决定要不要冒泡。

启动/测试：
  export XINCHAO_BRIDGE_MCP_TOKEN="你的心潮 MCP token"
  export XINCHAO_BRIDGE_HOST_TOKEN="你的宿主 external-chat token"
  export XINCHAO_BRIDGE_CHAT_ID="目标对话 ID"
  python3 http_wake.py            # 从 inbox/judge_request.json 取素材
  python3 http_wake.py --manual   # 用手动测试素材
  python3 http_wake.py --force    # 忽略最小间隔（测试用）
"""
import json, os, time, urllib.request, urllib.error

# ---- 全部走环境变量，不进仓库 ----
MCP_TOKEN = os.environ.get("XINCHAO_BRIDGE_MCP_TOKEN", "")
HOST_TOKEN = os.environ.get("XINCHAO_BRIDGE_HOST_TOKEN", "")
CHAT_ID = os.environ.get("XINCHAO_BRIDGE_CHAT_ID", "")
BASE_DIR = os.environ.get("XINCHAO_BRIDGE_BASE_DIR", os.path.expanduser("~/xinchao-bridge"))

MCP_URL = f"http://127.0.0.1:18110/mcp/{MCP_TOKEN}"
CONFIG_PATH = os.path.join(BASE_DIR, "config", "bridge_config.json")
LOG_PATH = os.path.join(BASE_DIR, "inbox", "http_wake.log")
STATE_PATH = os.path.join(BASE_DIR, "inbox", "http_wake.last")

HTTP_DEFAULTS = {
    "开启": True,
    "host": "127.0.0.1",
    "port": 8094,
    "path": "/api/external-chat",
    "最小唤醒间隔秒": 120,
    "唤醒模式": {
        "静默优先": True,
        "强信号冒泡关键词": ["手动互动", "urgent", "她在心潮等你"],
    },
}


def _log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    return line


def _load_cfg():
    cfg = dict(HTTP_DEFAULTS)
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, encoding="utf-8") as f:
                data = json.load(f)
            h = data.get("外部HTTP唤醒", {})
            if isinstance(h, dict):
                for k, v in h.items():
                    if k in HTTP_DEFAULTS:
                        cfg[k] = v
            m = data.get("唤醒模式", {})
            if isinstance(m, dict):
                mm = dict(HTTP_DEFAULTS["唤醒模式"])
                mm.update({k: v for k, v in m.items() if k in mm})
                cfg["唤醒模式"] = mm
    except Exception as e:
        _log(f"[config] 读取/初始化失败：{e}")
    return cfg


def _last_call():
    try:
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, encoding="utf-8") as f:
                return int(f.read().strip() or 0)
    except Exception:
        pass
    return 0


def _save_call(ts):
    try:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            f.write(str(ts))
    except Exception:
        pass


def _build_message(req):
    now = req.get("时间", time.strftime("%Y-%m-%d %H:%M"))
    xc = req.get("心潮底色", {})
    reason = (xc.get("原因") or "").strip()
    xc_msg = (xc.get("消息") or "").strip().replace("\n", " ")
    parts = [f"【心潮·唤醒】{now}"]
    if reason:
        parts.append(f"来源：{reason}")
    if xc_msg:
        parts.append(f"我的心潮：{xc_msg[:120]}")
    parts.append("——判断归我。")
    return "\n".join(parts)


def _put_to_box(req, msg):
    """静默路：塞进心潮黑匣子（surface=true），人类看不到，AI 下一轮自己读。"""
    if not MCP_TOKEN:
        _log("[box] 未配置 MCP token，跳过")
        return False
    now_local = req.get("时间", time.strftime("%Y-%m-%d %H:%M"))
    hhmm = now_local[-5:] if len(now_local) >= 5 else "--:--"
    args = {
        "action": "put",
        "text": msg,
        "kind": "event",
        "title": f"心潮·自主信号 {hhmm}",
        "surface": True,
        "expires_hours": 24,
    }
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
        "method": "tools/call",
        "params": {"name": "xinchao_box", "arguments": args},
    }, ensure_ascii=False).encode("utf-8")
    req_obj = urllib.request.Request(
        MCP_URL, data=body, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "xinchao-bridge/0.4"})
    try:
        with urllib.request.urlopen(req_obj, timeout=10) as resp:
            raw = resp.read(800).decode("utf-8", "replace")
        _log(f"[box] 静默塞匣成功: {raw[:100]}")
        return True
    except Exception as e:
        _log(f"[box] 塞匣失败：{e}")
        return False


def _bubble(req, cfg, msg):
    """冒泡路：宿主 external-chat 正门（强信号才用）。"""
    if not (HOST_TOKEN and CHAT_ID):
        _log("[bubble] 未配置宿主 token / chat_id，跳过")
        return False
    host = cfg["host"]
    port = int(cfg["port"])
    path = cfg["path"]
    body = json.dumps({
        "message": msg,
        "response-mode": "async-callback",
        "chat-id": CHAT_ID,
        "create-if-none": True
    }, ensure_ascii=False).encode("utf-8")
    req_obj = urllib.request.Request(
        f"http://{host}:{port}{path}", data=body, method="POST",
        headers={"Authorization": f"Bearer {HOST_TOKEN}",
                 "Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "xinchao-bridge/0.4"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req_obj, timeout=10) as resp:
            code = resp.status
            _ = resp.read(400).decode("utf-8", "replace")
        elapsed = time.time() - t0
        _log(f"[bubble] HTTP {code} {elapsed:.2f}s msg={msg[:70]}")
        return True
    except urllib.error.HTTPError as e:
        try:
            r = e.read(400).decode("utf-8", "replace")
        except Exception:
            r = ""
        _log(f"[bubble] HTTP {e.code} err={r[:200]}")
        return False
    except Exception as e:
        _log(f"[bubble] 请求异常：{e}")
        return False


def wake(req, force=False):
    """
    收到信封 → 递情报。
    默认静默（黑匣子 surface）；命中强信号关键词才冒泡。
    force=True 时忽略最小间隔，且强制走冒泡（手动测试用）。
    """
    if isinstance(req, str):
        try:
            with open(req, encoding="utf-8") as f:
                req = json.load(f)
        except Exception as e:
            _log(f"[wake] 素材文件读取失败：{e}")
            return False
    try:
        cfg = _load_cfg()
    except Exception as e:
        _log(f"[wake] 配置加载失败：{e}")
        return False
    if not cfg.get("开启", True):
        _log("[wake] 唤醒已关，跳过")
        return False

    now = int(time.time())
    last = _last_call()
    gap = cfg.get("最小唤醒间隔秒", 120)
    if (not force) and last and (now - last) < gap:
        _log(f"[wake] 距上次仅 {now-last}s < 阈值 {gap}s，跳过（防刷屏）")
        return False

    msg = _build_message(req)
    mode = cfg.get("唤醒模式", {})
    silent_first = bool(mode.get("静默优先", True))
    keywords = [k for k in (mode.get("强信号冒泡关键词") or []) if k]
    hit = any(k in msg for k in keywords)

    # 双保险：无论如何先塞盒子（兜底不丢），再决定要不要冒泡
    box_ok = _put_to_box(req, msg)
    if (not silent_first or hit or force) and box_ok:
        ok = _bubble(req, cfg, msg)
        _save_call(now)
        if ok:
            return True
        _log("[wake] 冒泡失败，盒子已兜底")
        return True
    if box_ok:
        _save_call(now)
        return True
    return _bubble(req, cfg, msg)


if __name__ == "__main__":
    import sys
    req_path = os.path.join(BASE_DIR, "inbox", "judge_request.json")
    force = "--force" in sys.argv
    if os.path.exists(req_path) and "--manual" not in sys.argv:
        with open(req_path, encoding="utf-8") as f:
            req = json.load(f)
    else:
        req = {"时间": time.strftime("%Y-%m-%d %H:%M"),
               "心潮底色": {"原因": "manual_test", "消息": "手动测试：静默链路自检，看到即回。"}}
    ok = wake(req, force=force)
    print("HTTP_WAKE_RESULT:", ok)