const form = document.getElementById("chatForm");
const sessionInput = document.getElementById("sessionId");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const messages = document.getElementById("messages");
const chips = document.querySelectorAll(".chip");

sessionInput.value = `session-${Date.now()}`;

function addMessage(text, role, meta = "") {
  const node = document.createElement("article");
  node.className = `msg ${role}`;
  node.textContent = text;

  if (meta) {
    const metaNode = document.createElement("div");
    metaNode.className = "meta";
    metaNode.textContent = meta;
    node.appendChild(metaNode);
  }

  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
}

async function sendMessage(message) {
  const sessionId = sessionInput.value.trim();
  if (!sessionId) {
    addMessage("Please enter a session id first.", "bot");
    return;
  }
  if (!message.trim()) {
    return;
  }

  addMessage(message, "user");
  sendBtn.disabled = true;

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        session_id: sessionId,
        message: message.trim(),
      }),
    });

    if (!response.ok) {
      const errBody = await response.text();
      addMessage(`Request failed (${response.status}). ${errBody}`, "bot");
      return;
    }

    const payload = await response.json();
    const model = payload.used_model || "unknown";
    addMessage(payload.reply || "No reply from assistant.", "bot", `model: ${model}`);
  } catch (error) {
    addMessage(`Network error: ${error}`, "bot");
  } finally {
    sendBtn.disabled = false;
    messageInput.focus();
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value;
  messageInput.value = "";
  await sendMessage(message);
});

chips.forEach((chip) => {
  chip.addEventListener("click", async () => {
    const text = chip.dataset.message || "";
    await sendMessage(text);
  });
});

addMessage(
  "Try: show menu, add 2 whopper, my address is 22 MG Road, payment options, use cod, checkout",
  "bot",
  "ready"
);
