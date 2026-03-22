const SESSION_ID = "s_" + Math.random().toString(36).slice(2, 10);

const appShell = document.getElementById("appShell");
const messagesEl = document.getElementById("messages");
const msgInput = document.getElementById("msgInput");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");
const promptChips = Array.from(document.querySelectorAll(".prompt-chip"));
const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
const urlInput = document.getElementById("urlInput");
const loadBtn = document.getElementById("loadBtn");
const closeBtn = document.getElementById("closeBtn");
const webFrame = document.getElementById("webFrame");
const webLoading = document.getElementById("webLoading");
const placeholder = document.getElementById("placeholder");
const chatPanel = document.getElementById("chatPanel");
const divider = document.getElementById("divider");
const webPanel = document.getElementById("webPanel");

const URL_RE = /(https?:\/\/[^\s<]+[^\s<.,;:!?])/gi;
const YOUTUBE_URL_RE = /https?:\/\/(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/|youtube\.com\/embed\/)([A-Za-z0-9_-]{8,15})[^\s<]*/gi;

function extractYoutubeIds(text) {
  const ids = [];
  if (!text) {
    return ids;
  }

  const matched = text.matchAll(YOUTUBE_URL_RE);
  for (const m of matched) {
    const id = (m[1] || "").trim();
    if (!id || ids.includes(id)) {
      continue;
    }
    ids.push(id);
    if (ids.length >= 10) {
      break;
    }
  }

  return ids;
}

function buildYoutubeEmbeds(content) {
  const ids = extractYoutubeIds(content);
  if (!ids.length) {
    return "";
  }

  const cards = ids
    .map(
      (id) => `
      <div class="yt-card">
        <iframe
          src="https://www.youtube.com/embed/${id}"
          title="YouTube video ${id}"
          loading="lazy"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          referrerpolicy="strict-origin-when-cross-origin"
          allowfullscreen
        ></iframe>
      </div>`
    )
    .join("");

  return `<div class="yt-grid">${cards}</div>`;
}

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
  const youtubeEmbeds = role === "bot" ? buildYoutubeEmbeds(content) : "";
  wrap.innerHTML = `
    <div class="msg-avatar">${avatarLabel}</div>
    <div class="msg-content">
      <div class="bubble">${md(content)}${youtubeEmbeds}</div>
    </div>`;

  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setMobileView(target) {
  if (!appShell) {
    return;
  }

  appShell.classList.toggle("mode-chat", target === "chat");
  appShell.classList.toggle("mode-web", target === "web");
  tabButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.target === target);
  });
}

function updateSendState(isSending = false) {
  const hasText = msgInput.value.trim().length > 0;
  sendBtn.disabled = isSending || !hasText;
  sendBtn.classList.toggle("is-loading", isSending);
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
  if (!text || sendBtn.classList.contains("is-loading")) {
    return;
  }

  renderBubble("user", text);
  msgInput.value = "";
  msgInput.style.height = "auto";
  updateSendState(true);
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
    updateSendState(false);
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
  updateSendState(false);
});

promptChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    msgInput.value = chip.dataset.prompt || "";
    msgInput.dispatchEvent(new Event("input"));
    msgInput.focus();
  });
});

clearBtn.addEventListener("click", async () => {
  if (!window.confirm("Ban muon xoa toan bo lich su chat?")) {
    return;
  }

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

  try {
    const parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol)) {
      return "";
    }
    return parsed.toString();
  } catch {
    return "";
  }
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
    renderBubble("bot", "URL khong hop le. Hay dung dinh dang https://tenmien", null);
    return;
  }

  webLoading?.classList.add("show");
  webFrame.src = url;
  webFrame.style.display = "block";
  placeholder.style.display = "none";
  urlInput.value = url;

  if (window.innerWidth <= 900) {
    setMobileView("web");
  }
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
  webLoading?.classList.remove("show");

  if (window.innerWidth <= 900) {
    setMobileView("chat");
  }
});

webFrame.addEventListener("load", () => {
  webLoading?.classList.remove("show");
});

tabButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setMobileView(button.dataset.target || "chat");
  });
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

updateSendState(false);
