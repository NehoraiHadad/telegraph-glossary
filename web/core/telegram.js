// Telegram Bot API (CORS-enabled). The bot token is the user's own and
// stays in their browser.

export async function botCall(token, method, params = {}) {
  const res = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  const data = await res.json().catch(() => ({ ok: false, description: `HTTP ${res.status}` }));
  if (!data.ok) throw new Error(data.description || "Telegram error");
  return data.result;
}

export const getMe = (token) => botCall(token, "getMe");

export function sendHtml(token, chatId, html, { preview = false } = {}) {
  return botCall(token, "sendMessage", {
    chat_id: chatId,
    text: html,
    parse_mode: "HTML",
    link_preview_options: { is_disabled: !preview },
  });
}

/** Chats the bot has seen recently: channels/groups it was added to + people who wrote to it. */
export async function discoverChats(token) {
  const updates = await botCall(token, "getUpdates", {
    allowed_updates: ["message", "channel_post", "my_chat_member"],
  });
  const chats = new Map();
  for (const u of updates) {
    const chat = (u.my_chat_member || u.message || u.channel_post || {}).chat;
    if (!chat) continue;
    const name = chat.title || [chat.first_name, chat.last_name].filter(Boolean).join(" ") || chat.username;
    chats.set(String(chat.id), { id: String(chat.id), name, type: chat.type });
  }
  return [...chats.values()];
}
