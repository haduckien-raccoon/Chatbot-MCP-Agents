const SESSION_ID = "s_" + Math.random().toString(36).slice(2, 10);

const messagesEl = document.getElementById("messages");
const msgInput = document.getElementById("msgInput");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");
const urlInput = document.getElementById("urlInput");
const loadBtn = document.getElementById("loadBtn");
const closeBtn = document.getElementById("closeBtn");
const webFrame = document.getElementById("webFrame");
const placeholder = document.getElementById("placeholder");
const chatPanel = document.getElementById("chatPanel");
const divider = document.getElementById("divider");
const webPanel = document.getElementById("webPanel");

const URL_RE = /(https?:\/\/[^\s<]+[^\s<.,;:!?])/gi;

function renderBubble(role, content, agentUsed) {
  if (agentUsed && role === "bot") {
    const tag = document.createElement("div");
    tag.className = "agent-tag";
    tag.textContent = `[] routed -> ${agentUsed.replace(/_/g, " ")}`;
    messagesEl.appendChild(tag);
  }

  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const avatarLabel = role === "user" ? "Ban" : "SG";
  wrap.innerHTML = `
    <div class="msg-avatar">${avatarLabel}</div>
    <div class="msg-content">
      <div class="bubble">${md(content)}</div>
    </div>`;

  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function showTyping() {
  const el = document.createElement("div");
  el.className = "msg bot typing";
  el.id = "typing";
  el.innerHTML = `<div class="msg-avatar">SG</div>
    <div class="msg-content"><div class="bubble">
      <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    </div></div>`;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideTyping() {
  document.getElementById("typing")?.remove();
}

async function send() {
  const text = msgInput.value.trim();
  if (!text) {
    return;
  }

  renderBubble("user", text);
  msgInput.value = "";
  msgInput.style.height = "auto";
  sendBtn.disabled = true;
  showTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: SESSION_ID }),
    });

    const data = await res.json();
    hideTyping();
    renderBubble("bot", data.reply, data.agent_used);
  } catch {
    hideTyping();
    renderBubble("bot", "Loi ket noi. Vui long thu lai.", null);
  } finally {
    sendBtn.disabled = false;
    msgInput.focus();
  }
}

sendBtn.addEventListener("click", send);
msgInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

msgInput.addEventListener("input", () => {
  msgInput.style.height = "auto";
  msgInput.style.height = Math.min(msgInput.scrollHeight, 120) + "px";
});

clearBtn.addEventListener("click", async () => {
  await fetch(`/api/chat/${SESSION_ID}`, { method: "DELETE" });
  messagesEl.innerHTML = `<div class="msg bot">
    <div class="msg-avatar">SG</div>
    <div class="msg-content"><div class="bubble">Da xoa lich su hoi thoai.</div></div></div>`;
});

function md(text) {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/```(\w+)?\n([\s\S]*?)```/g, "<pre><code>$2</code></pre>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a class="chat-link" href="$2" rel="noopener noreferrer">$1</a>'
    )
    .replace(URL_RE, '<a class="chat-link" href="$1" rel="noopener noreferrer">$1</a>')
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/\n/g, "<br>");

  return escaped;
}

function normalizeUrl(raw) {
  let url = (raw || "").trim();
  if (!url) {
    return "";
  }

  if (!/^https?:\/\//i.test(url)) {
    url = "https://" + url;
  }

  return url;
}

function pulsePreviewPanel() {
  webPanel.classList.remove("is-active-preview");
  // Trigger animation each time a link is opened from chat.
  void webPanel.offsetWidth;
  webPanel.classList.add("is-active-preview");
}

function loadUrl(rawUrl = "") {
  const url = normalizeUrl(rawUrl || urlInput.value);
  if (!url) {
    return;
  }

  webFrame.src = url;
  webFrame.style.display = "block";
  placeholder.style.display = "none";
  urlInput.value = url;
}

messagesEl.addEventListener("click", (event) => {
  const link = event.target.closest("a.chat-link");
  if (!link) {
    return;
  }

  event.preventDefault();
  loadUrl(link.getAttribute("href") || "");
  pulsePreviewPanel();
});

loadBtn.addEventListener("click", loadUrl);
urlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    loadUrl();
  }
});

closeBtn.addEventListener("click", () => {
  webFrame.src = "";
  webFrame.style.display = "none";
  placeholder.style.display = "flex";
  urlInput.value = "";
});

let dragging = false;

divider.addEventListener("mousedown", (e) => {
  dragging = true;
  e.preventDefault();
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
});

document.addEventListener("mousemove", (e) => {
  if (!dragging || window.innerWidth <= 900) {
    return;
  }

  const rect = document.querySelector(".app").getBoundingClientRect();
  const w = Math.max(280, Math.min(e.clientX - rect.left, rect.width - 250));
  chatPanel.style.width = w + "px";
});

document.addEventListener("mouseup", () => {
  dragging = false;
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
});
