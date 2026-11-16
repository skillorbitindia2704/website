(() => {
  const root = document.getElementById("orbit-chatbot");
  if (!root) return;
  const panel = document.getElementById("orbit-chat-panel");
  const launcher = document.getElementById("orbit-chat-launcher");
  const close = document.getElementById("orbit-chat-close");
  const form = document.getElementById("orbit-chat-form");
  const input = document.getElementById("orbit-chat-input");
  const messagesEl = document.getElementById("orbit-chat-messages");
  const suggestions = document.getElementById("orbit-chat-suggestions");
  const history = [];

  function addMessage(text, role, extraClass) {
    const row = document.createElement("div");
    row.className = "orbit-chat-message " + role + (extraClass ? " " + extraClass : "");
    const bubble = document.createElement("div");
    bubble.className = "orbit-chat-bubble";
    bubble.textContent = text;
    row.appendChild(bubble);
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return row;
  }

  function toggle(open) {
    panel.hidden = !open;
    launcher.setAttribute("aria-expanded", String(open));
    if (open) input.focus();
  }
  launcher.addEventListener("click", () => toggle(panel.hidden));
  close.addEventListener("click", () => toggle(false));

  async function sendMessage(message) {
    const clean = (message || "").trim();
    if (!clean || form.querySelector("button").disabled) return;
    if (suggestions) suggestions.remove();
    addMessage(clean, "user");
    history.push({ role: "user", text: clean });
    input.value = "";
    const sendButton = form.querySelector("button");
    sendButton.disabled = true;
    const typing = addMessage("Orbit is typing…", "assistant", "typing");
    try {
      const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
      const response = await fetch(root.dataset.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ messages: history.slice(-10) })
      });
      const data = await response.json().catch(() => ({}));
      typing.remove();
      if (!response.ok) throw new Error(data.error || "The assistant is temporarily unavailable.");
      const reply = data.reply || "Sorry, I couldn't generate a reply.";
      addMessage(reply, "assistant");
      history.push({ role: "model", text: reply });
      if (history.length > 10) history.splice(0, history.length - 10);
    } catch (error) {
      typing.remove();
      addMessage(error.message || "Something went wrong. Please try again.", "assistant");
    } finally {
      sendButton.disabled = false;
      input.focus();
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage(input.value);
  });
  if (suggestions) {
    suggestions.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-question]");
      if (button) sendMessage(button.dataset.question);
    });
  }
})();