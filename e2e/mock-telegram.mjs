// Minimal fake Telegram Bot API: records every call, answers like Telegram would.
import http from "node:http";
import fs from "node:fs";
const log = process.argv[2];
http.createServer((req, res) => {
  let body = "";
  req.on("data", (c) => (body += c));
  req.on("end", () => {
    const method = req.url.split("/").pop();
    const params = body ? JSON.parse(body) : {};
    fs.appendFileSync(log, JSON.stringify({ method, params }) + "\n");
    let result = true;
    if (method === "getMe") result = { id: 1, is_bot: true, username: "TestGlossBot" };
    if (method.startsWith("edit") || method === "sendMessage") result = { message_id: params.message_id || 1, chat: { id: params.chat_id } };
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ ok: true, result }));
  });
}).listen(8899, "127.0.0.1");
