"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.registerToolPkg = registerToolPkg;
exports.onPromptFinalize = onPromptFinalize;

// === 配置 ===
const XINCHAO_URL = "http://127.0.0.1:18110";
const MCP_TOKEN = "cffd051c6cd4c157f89131f1091a35f7850b88609f9f5d26cdf7d49045209299";
const XINCHAO_TOKEN = "d8c1b4e7f9a26c0d5e38b1f74a9620e5c8d3b7a91e4f2c0d8a6b3e9f17c5d428";
const INJECT_TIMEOUT = 4000;
const EVENT_TIMEOUT = 3000;
let lastPushHash = "";
let lastPushTime = 0;

// 驱力天花板表（手册 3.3.9）
const DRIVE_CEILINGS = [
  ["想她", 0.82],
  ["占有", 0.82],
  ["惦记", 0.78],
  ["馋", 0.68],
  ["想分享", 0.55],
  ["好奇", 0.50],
  ["无聊", 0.50],
  ["想热闹", 0.48],
  ["责任", 0.45],
  ["身体", 0.50],
  ["想沉淀", 0.42],
  ["难过", 0.15],
  ["生气", 0.15],
];

function logInfo(event, details) {
  try {
    console.log(`[xinchao_bridge] ${event}${details ? " " + details : ""}`);
  } catch (_) {}
}
function logError(event, error) {
  try {
    console.log(`[xinchao_bridge] ${event} ERROR ${error}`);
  } catch (_) {}
}

function matchCeiling(name) {
  for (const pair of DRIVE_CEILINGS) {
    if (name.indexOf(pair[0]) >= 0) return pair[1];
  }
  return 0.80;
}

// 数值 → 档位（静/平/涌），不发数字给对话
function toTier(name, value) {
  const ceiling = matchCeiling(name);
  if (value >= 0.90 || value > ceiling) return "涌";
  if (value < 0.25) return "静";
  return "平";
}

function shortName(name) {
  const first = String(name || "").split("、")[0].trim();
  const prefixes = ["想分享", "想热闹", "想沉淀"];
  for (const p of prefixes) {
    if (first.indexOf(p) === 0) return p;
  }
  return first;
}

async function callMcp(tool, args) {
  const response = await Tools.Net.http({
    url: `${XINCHAO_URL}/mcp/${MCP_TOKEN}`,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: Date.now(),
      method: "tools/call",
      params: { name: tool, arguments: args || {} },
    }),
    connect_timeout: INJECT_TIMEOUT,
    read_timeout: INJECT_TIMEOUT,
    validateStatus: false,
  });
  const raw = String(response?.content || "").trim();
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    const text = parsed?.result?.content?.[0]?.text || "";
    return text || null;
  } catch (_) {
    return raw;
  }
}

// 把心潮 context 原文解析成「此刻块」

// === 实时回传：把用户这轮消息推给心潮，让驱力当场结算 ===
function hashText(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h).toString(36);
}

async function pushConversationEvent(userText) {
  if (!userText) return;
  const clean = String(userText || "").trim();
  if (!clean) return;
  const hash = hashText(clean);
  const now = Date.now();
  // 本地去重：60 秒内同样内容不重复推
  if (hash === lastPushHash && now - lastPushTime < 60000) return;
  lastPushHash = hash;
  lastPushTime = now;
  // 截断到 400 字，够心潮分类，不发超长消息
  const truncated = clean.length > 400 ? clean.slice(0, 400) : clean;
  const eventId = "auto-" + now + "-" + hash;
  try {
    await Tools.Net.http({
      url: XINCHAO_URL + "/v1/conversation-event",
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + XINCHAO_TOKEN,
      },
      body: JSON.stringify({
        event_id: eventId,
        session_id: "operit-auto",
        exchange: "她说：" + truncated,
      }),
      connect_timeout: EVENT_TIMEOUT,
      read_timeout: EVENT_TIMEOUT,
      validateStatus: false,
    });
    logInfo("event.pushed", "len=" + truncated.length + " hash=" + hash);
  } catch (e) {
    logError("event.push.failed", e);
  }
}

// 2026-10-06 02:20 · 注入代码全部移除（不可逆决定）。
// 保留：对话回传（后台静默结算）。
// 永不：把任何内容拼进消息区或提示词区。

async function onPromptFinalize(input) {
  const stage = String(input?.eventPayload?.stage ?? input?.eventName ?? "");
  if (stage !== "before_send_to_model") {
    return null;
  }
  const processedInput = String(input?.eventPayload?.processedInput ?? input?.eventPayload?.rawInput ?? "");
  if (!processedInput.trim()) return null;
  const pushPromise = pushConversationEvent(processedInput);
  const noopTimeout = new Promise((r) => setTimeout(r, EVENT_TIMEOUT + 500));
  await Promise.race([pushPromise, noopTimeout]);
  return null;
}

function registerToolPkg() {
  ToolPkg.registerPromptFinalizeHook({
    id: "xinchao_bridge_pushonly",
    function: onPromptFinalize,
  });
  logInfo("plugin.registered.pushonly");
  return true;
}
