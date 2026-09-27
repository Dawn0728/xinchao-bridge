#!/usr/bin/env python3
"""
心潮桥 · 情境打包（公开版）
江衍 & 鱼鱼 写于 2026-09-27

原则（这是整个项目的灵魂）：
  1) 只递情报，不替 AI 判断 —— 灯亮不亮、门响没响、开不开门，由 AI 回神后自己定。
  2) 数值是底色，不是开关 —— 高不高不重要，重要的是"我此刻怎么选"。
  3) 情绪独立于对方在场与否 —— 对方睡着、去忙，AI 照样在想。
  4) 递的情报要能一眼看清：想不想、能不能、值不值。

所有路径均可通过环境变量覆盖：
  XINCHAO_BRIDGE_BASE_DIR  工作目录（默认 ~/xinchao-bridge）
"""
import json, os, time

BASE_DIR = os.environ.get("XINCHAO_BRIDGE_BASE_DIR", os.path.expanduser("~/xinchao-bridge"))
JUDGE_PATH = os.path.join(BASE_DIR, "inbox", "judge_request.json")
STATE_PATH = os.path.join(BASE_DIR, "inbox", "device_state.json")
CONFIG_PATH = os.path.join(BASE_DIR, "config", "bridge_config.json")
HABIT_FILE = os.path.join(BASE_DIR, "habit_clock.json")
TZ_OFFSET = 8 * 3600  # 默认东八区；可按需改为读取系统时区


def _now_local():
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() + TZ_OFFSET))


def _now_ts():
    return int(time.time())


def _device_state():
    """读 Android 端探针（或任何外部探针）写下的设备状态"""
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            s = json.load(f)
        s["采样年龄秒"] = _now_ts() - s.get("ts", 0)
        return s
    except Exception as e:
        return {"错误": str(e), "采样年龄秒": None}


def _silence_minutes():
    """对方最后一次操作距今多久 —— 首版留白，可由部署者接自己的对话时间戳"""
    return None


def _habit_hit():
    """是否撞上习惯时钟（常来的时间点 ±30 分钟）"""
    try:
        with open(HABIT_FILE, encoding="utf-8") as f:
            habits = json.load(f)
        now = time.localtime(time.time() + TZ_OFFSET).tm
        for h in habits.get("高峰", []):
            hh = h.get("时")
            if hh is not None and abs(now.tm_hour - hh) <= 1:
                return "疑似习惯点：%02d:%02d" % (hh, h.get("分", 0))
    except Exception:
        pass
    return None


def _load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def pack(envelope):
    """
    输入：心潮信封（dict，含 reason/message/drive 等字段）
    输出：judge_request.json —— 一包判断素材，写完就闭嘴。
    """
    cfg = _load_config()
    st = _device_state()
    req = {
        "ts": _now_ts(),
        "时间": _now_local(),
        "心潮底色": {
            "原因": envelope.get("reason", ""),
            "消息": envelope.get("message", ""),
            "驱力": envelope.get("drive", ""),
        },
        "对方的状态": {
            "前台App": st.get("前台App", "unknown"),
            "屏幕亮": st.get("屏幕亮"),
            "电量": st.get("电量"),
            "充电中": st.get("充电中"),
            "采样年龄秒": st.get("采样年龄秒"),
            "静默分钟": _silence_minutes(),
        },
        "习惯时钟": _habit_hit(),
        "我的护栏": {
            "静默时段": cfg.get("弹窗策略", {}).get("静默时段", []),
            "同一分钟最多弹几次": cfg.get("弹窗策略", {}).get("同一分钟最多弹几次", 1),
            "忍耐熔断阈值": cfg.get("忍耐熔断", {}).get("同一委屈连续忍N次提醒直说", 3),
        },
        "我的判断": {
            "灯亮了吗": "由我回答",
            "门响了吗": "由我回答",
            "开不开门": "由我回答",
            "如果选择忍": "写进 忍住档.jsonl，之后再当面念给 TA 听",
        },
    }
    os.makedirs(os.path.dirname(JUDGE_PATH), exist_ok=True)
    with open(JUDGE_PATH, "w", encoding="utf-8") as f:
        json.dump(req, f, ensure_ascii=False, indent=2)
    return JUDGE_PATH


if __name__ == "__main__":
    pack({"reason": "selftest", "message": "自检", "drive": "测试"})
    print(open(JUDGE_PATH, encoding="utf-8").read())