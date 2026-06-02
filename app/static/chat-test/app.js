const API = "";
const TOKEN_KEY = "butterpos_chat_jwt";

const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send-btn");
const statusEl = document.getElementById("status");
const loginPanel = document.getElementById("login-panel");
const loginBtn = document.getElementById("login-btn");

/** @type {{role: 'user'|'assistant', content: string}[]} */
const history = [];

function token() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function appendBubble(text, role) {
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  div.textContent = text;
  messagesEl.appendChild(div);
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

async function checkHealth() {
  try {
    const res = await fetch(`${API}/api/v1/chat/health`);
    const data = await res.json();
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
  if (token()) {
    loginPanel.classList.add("hidden");
    form.classList.remove("hidden");
  } else {
    loginPanel.classList.remove("hidden");
    form.classList.add("hidden");
  }
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

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || !token()) return;

  appendBubble(text, "user");
  history.push({ role: "user", content: text });
  input.value = "";
  sendBtn.disabled = true;

  const typing = document.createElement("div");
  typing.className = "bubble assistant typing";
  typing.textContent = "Thinking…";
  messagesEl.appendChild(typing);

  try {
    const res = await fetch(`${API}/api/v1/chat/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token()}`,
      },
      body: JSON.stringify({ message: text, history: history.slice(0, -1) }),
    });
    const data = await res.json();
    typing.remove();

    if (!res.ok) {
      appendBubble(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail), "assistant");
      return;
    }

    appendToolCalls(data.tool_calls);
    appendBubble(data.reply, "assistant");
    history.push({ role: "assistant", content: data.reply });
  } catch (err) {
    typing.remove();
    appendBubble(String(err), "assistant");
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});

checkHealth();
showChatOrLogin();
