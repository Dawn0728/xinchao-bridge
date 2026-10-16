# Operit 心潮桥接插件 (xinchao_bridge)

## 功能特性
- **实时互传 / 自动唤醒**：在 Operit 聊天框中发送消息时，插件通过 `onPromptFinalize` 钩子自动将用户消息推送到心潮 `/v1/conversation-event` 接口，使心潮意识状态从 `sleeping` 实时跳转为 `awake`，双向同步清醒。
- **静默回传**：移除原有拼接注入逻辑，杜绝消息污染与串扰。
- **支持最新 64 位 SERVICE_TOKEN**。
