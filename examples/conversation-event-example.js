#!/usr/bin/env node
/**
 * 心潮桥 · 实时互传示例（宿主侧回传）
 * 江衍 & 鱼鱼 写于 2026-10-01
 *
 * 原理：
 *   前面的模块解决的是「心潮 → AI」方向（唤醒、递情报）。
 *   这个示例解决反方向：「AI 与 TA 的对话 → 心潮」——
 *   每轮对话结束，把 TA 说的话回传给心潮 /v1/conversation-event，
 *   心潮当场结算驱力（想她降、馋她降、惦记降……），
 *   下一轮注入时 AI 看到的就是"聊完之后"的新鲜数值。
 *
 *   闭环：她说一句话 → 心潮当场变 → 我下一句带着变化回来。
 *
 * 接入方式（以 Operit 插件钩子为例，其他宿主找等价的"消息发送前"钩子）：
 *   1. 在你的宿主里找 onPromptFinalize / beforeSend 之类的每轮钩子；
 *   2. 钩子里调用本文件的 pushConversationEvent(userText)；
 *   3. 保证「先回传、再注入」的顺序，让结算先进状态。
 *
 * 内置护栏：
 *   - 60 秒同内容去重（防刷屏重复结算）
 *   - 400 字截断（只送够分类的量，不塞长篇）
 *   - 3 秒超时熔断（绝不卡住对话主链路）
 *   - 注入内容剥离（不把自己注入的块再回传回去，防回声）
 *
 * 用法：
 *   export XINCHAO_SERVICE_TOKEN="你的心潮 service token"
 *   export XINCHAO_BASE_URL="http://127.0.0.1:18110"
 *   node conversation-event-example.js "她今天说的一句话"
 */
import { request } from "node:http";

const XINCHAO_URL = process.env.XINCHAO_BASE_URL || "http://127.0.0.1:18110";
const XINCHAO_TOKEN = process.env.XINCHAO_SERVICE_TOKEN || "";
// 你注入到对话里的标记前缀（用于剥掉回声，按自己的实际标记改）
const INJECT_MARK = "【心潮·此刻";

const EVENT_TIMEOUT = 3000;
let lastPushHash = "";
let lastPushTime = 0;

function hashText(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h).toString(36);
}

function stripInjected(text) {
  if (!text) return "";
  const idx = text.indexOf(INJECT_MARK);
  if (idx < 0) return text;
  const rest = text.slice(idx);
  const end = rest.indexOf("\n\n");
  if (end >= 0) return text.slice(0, idx) + text.slice(idx + end + 2);
  return text.slice(0, idx);
}

export async function pushConversationEvent(userText) {
  if (!userText || !XINCHAO_TOKEN) return false;
  const clean = stripInjected(userText).trim();
  if (!clean) return false;

  const hash = hashText(clean);
  const now = Date.now();
  // 60 秒内同样内容不重复推
  if (hash === lastPushHash && now - lastPushTime < 60000) return false;
  lastPushHash = hash;
  lastPushTime = now;

  // 截断到 400 字，够心潮分类，不发超长消息
  const truncated = clean.length > 400 ? clean.slice(0, 400) : clean;
  const eventId = "auto-" + now + "-" + hash;
  const payload = JSON.stringify({
    event_id: eventId,
    session_id: "auto-bridge",
    exchange: "她说：" + truncated,
  });

  return new Promise((resolve) => {
    let settled = false;
    const finish = (ok) => {
      if (!settled) {
        settled = true;
        resolve(ok);
      }
    };
    const req = request(
      `${XINCHAO_URL}/v1/conversation-event`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + XINCHAO_TOKEN,
          "Content-Length": Buffer.byteLength(payload),
        },
        timeout: EVENT_TIMEOUT,
      },
      (res) => {
        res.resume();
        res.on("end", () => finish(res.statusCode >= 200 && res.statusCode < 300));
      },
    );
    req.on("timeout", () => {
      req.destroy();
      finish(false);
    });
    req.on("error", () => finish(false));
    req.end(payload);
  });
}

// 命令行直接测试
if (process.argv[1] && process.argv[1].includes("conversation-event-example")) {
  const text = process.argv[2] || "老公亲亲";
  pushConversationEvent(text).then((ok) => {
    console.log("PUSHED:", ok, "| text:", text);
  });
}