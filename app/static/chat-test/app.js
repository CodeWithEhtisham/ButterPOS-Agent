const API = "";
const TOKEN_KEY = "butterpos_chat_jwt";
const CONVERSATION_KEY = "butterpos_chat_conversation_id";

const SENDER_LABELS = {
  customer: "You",
  ai: "AI Assistant",
  human: "Support Agent",
};

const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send-btn");
const statusEl = document.getElementById("status");
const loginPanel = document.getElementById("login-panel");
const loginBtn = document.getElementById("login-btn");
const logoutBtn = document.getElementById("logout-btn");
const humanActiveBanner = document.getElementById("human-active-banner");

/** @type {{role: 'user'|'assistant', content: string}[]} */
const history = [];
let conversationId = localStorage.getItem(CONVERSATION_KEY) || "";
let messageCount = 0;
let pollTimer = null;
let escalated = false;
let humanActiveBannerShown = false;

function token() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

function setConversationId(id) {
  conversationId = id || "";
  if (conversationId) {
    localStorage.setItem(CONVERSATION_KEY, conversationId);
  } else {
    localStorage.removeItem(CONVERSATION_KEY);
  }
}

/** Client-side expiry check only — server still validates signature. */
function isTokenUsable(jwt) {
  if (!jwt || jwt.split(".").length !== 3) return false;
  try {
    const payload = JSON.parse(
      atob(jwt.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))
    );
    if (typeof payload.exp !== "number") return false;
    return payload.exp * 1000 > Date.now() + 5000;
  } catch {
    return false;
  }
}

function setHumanAgentActive(active) {
  escalated = active;
  if (!humanActiveBanner) return;
  humanActiveBanner.classList.toggle("hidden", !active);
  if (active) {
    statusEl.textContent = "Human support agent is active";
    statusEl.className = "status ok";
  }
}

function appendSystemNotice(text) {
  const group = document.createElement("div");
  group.className = "msg-group system";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  group.appendChild(bubble);
  messagesEl.appendChild(group);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function appendBubble(text, role, speaker) {
  const content = (text || "").trim();
  if (!content) return;

  const group = document.createElement("div");
  const isUser = role === "user";
  const isHuman = speaker === "human";
  const isAi = !isUser && !isHuman;

  group.className = "msg-group";
  if (isUser) {
    group.classList.add("outgoing");
  } else {
    group.classList.add("incoming");
    if (isHuman) group.classList.add("human");
    if (isAi) group.classList.add("ai");
  }

  const labelKey = isUser ? "customer" : isHuman ? "human" : "ai";
  const sender = document.createElement("div");
  sender.className = "msg-sender";
  sender.textContent = SENDER_LABELS[labelKey];
  group.appendChild(sender);

  const bubble = document.createElement("div");
  bubble.className = `bubble ${isHuman ? "human" : role}`;
  bubble.textContent = content;
  group.appendChild(bubble);

  messagesEl.appendChild(group);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function appendToolCalls(toolCalls) {
  if (!toolCalls?.length) return;
  const details = document.createElement("details");
  details.className = "tool-block";
  details.open = true;
  const summary = document.createElement("summary");
  summary.textContent = `MCP tools (${toolCalls.length})`;
  details.appendChild(summary);
  const pre = document.createElement("pre");
  pre.textContent = toolCalls
    .map(
      (t) =>
        `${t.success ? "✓" : "✗"} ${t.tool_name}(${JSON.stringify(t.arguments)})\n→ ${t.result.slice(0, 400)}`
    )
    .join("\n\n");
  details.appendChild(pre);
  messagesEl.appendChild(details);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function startPolling() {
  stopPolling();
  if (!conversationId || !token()) return;
  pollTimer = setInterval(() => {
    pollSession().catch(() => {});
  }, 3000);
}

async function pollSession() {
  if (!conversationId || !token()) return;
  const res = await fetch(
    `${API}/api/v1/chat/sessions/${encodeURIComponent(conversationId)}?since_index=${messageCount}`,
    { headers: { Authorization: `Bearer ${token()}` } }
  );
  if (res.status === 401) {
    clearToken();
    stopPolling();
    showChatOrLogin();
    return;
  }
  if (!res.ok) return;
  const data = await res.json();
  messageCount = data.message_count;
  if (data.status === "escalated") {
    setHumanAgentActive(true);
  }
  for (const turn of data.messages || []) {
    if (turn.role === "user") {
      continue;
    }
    appendBubble(turn.content, "assistant", turn.speaker);
    history.push({ role: "assistant", content: turn.content });
  }
}

async function checkHealth() {
  try {
    const res = await fetch(`${API}/api/v1/chat/health`);
    const data = await res.json();
    if (escalated) {
      return;
    }
    if (data.ready) {
      statusEl.textContent = `Ready · ${data.model} · ${data.mcp_tools} MCP tools`;
      statusEl.className = "status ok";
    } else {
      statusEl.textContent = "Configure OPENROUTER_API_KEY and MCP_SERVER_URL";
      statusEl.className = "status err";
    }
  } catch {
    statusEl.textContent = "Middleware not reachable on this host";
    statusEl.className = "status err";
  }
}

function showChatOrLogin() {
  const jwt = token();
  if (isTokenUsable(jwt)) {
    loginPanel.classList.add("hidden");
    form.classList.remove("hidden");
    logoutBtn.classList.remove("hidden");
    if (escalated) {
      setHumanAgentActive(true);
      startPolling();
    }
    return;
  }
  if (jwt) clearToken();
  stopPolling();
  setHumanAgentActive(false);
  humanActiveBannerShown = false;
  loginPanel.classList.remove("hidden");
  form.classList.add("hidden");
  logoutBtn.classList.add("hidden");
}

loginBtn.addEventListener("click", async () => {
  const client_id = document.getElementById("client-id").value.trim();
  const client_secret = document.getElementById("client-secret").value.trim();
  const subject = document.getElementById("subject").value.trim() || "demo-staff";
  if (!client_id || !client_secret) return;

  const res = await fetch(`${API}/api/v1/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id, client_secret, subject }),
  });
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "Login failed");
    return;
  }
  localStorage.setItem(TOKEN_KEY, data.access_token);
  showChatOrLogin();
});

logoutBtn.addEventListener("click", () => {
  clearToken();
  setConversationId("");
  history.length = 0;
  messageCount = 0;
  escalated = false;
  humanActiveBannerShown = false;
  stopPolling();
  setHumanAgentActive(false);
  messagesEl.innerHTML = "";
  showChatOrLogin();
  checkHealth();
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || !token()) return;

  appendBubble(text, "user", "customer");
  history.push({ role: "user", content: text });
  input.value = "";
  sendBtn.disabled = true;

  const typing = document.createElement("div");
  typing.className = escalated ? "msg-group system" : "msg-group incoming ai";
  const typingBubble = document.createElement("div");
  typingBubble.className = escalated ? "bubble typing" : "bubble assistant typing";
  typingBubble.textContent = escalated ? "Sending…" : "Thinking…";
  typing.appendChild(typingBubble);
  messagesEl.appendChild(typing);

  try {
    const payload = {
      message: text,
      history: history.slice(0, -1),
      conversation_id: conversationId || undefined,
    };
    const res = await fetch(`${API}/api/v1/chat/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token()}`,
      },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    typing.remove();

    if (!res.ok) {
      if (res.status === 401) {
        clearToken();
        showChatOrLogin();
        appendBubble("Session expired or invalid — click Get token to sign in again.", "assistant", "ai");
        return;
      }
      appendBubble(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail), "assistant", "ai");
      return;
    }

    if (data.conversation_id) {
      setConversationId(data.conversation_id);
    }
    if (typeof data.message_count === "number") {
      messageCount = data.message_count;
    } else if (data.forwarded_to_human) {
      messageCount += 1;
    } else {
      messageCount += 2;
    }

    if (data.escalated || data.forwarded_to_human) {
      setHumanAgentActive(true);
      startPolling();
      if (data.escalated && !humanActiveBannerShown) {
        humanActiveBannerShown = true;
        appendSystemNotice(
          "A human support agent is now handling this conversation. You can keep messaging here."
        );
      }
    }

    if (!data.forwarded_to_human) {
      appendToolCalls(data.tool_calls);
    }

    const reply = (data.reply || "").trim();
    const isAck =
      reply === "Your message was sent to the support agent." ||
      reply.toLowerCase().includes("sent to the support agent");

    if (reply && !(data.forwarded_to_human && isAck)) {
      appendBubble(reply, "assistant", "ai");
      history.push({ role: "assistant", content: reply });
    }

    if (typeof data.message_count === "number") {
      messageCount = data.message_count;
    }
  } catch (err) {
    typing.remove();
    appendBubble(String(err), "assistant", "ai");
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});

checkHealth();
showChatOrLogin();
