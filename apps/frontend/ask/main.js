function addBubble(role, text, tool) {
  const chat = document.getElementById("chat");
  const el = document.createElement("article");
  el.className = `bubble ${role}`;
  if (tool) {
    const meta = document.createElement("div");
    meta.className = "tool";
    meta.textContent = `tool: ${tool}`;
    el.appendChild(meta);
  }
  const body = document.createElement("div");
  body.textContent = text;
  el.appendChild(body);
  chat.appendChild(el);
  el.scrollIntoView({ behavior: "smooth", block: "end" });
}

async function ask(question) {
  addBubble("user", question);
  const response = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question })
  });
  if (!response.ok) {
    addBubble("assistant", "The current view could not answer that yet.");
    return;
  }
  const data = await response.json();
  addBubble("assistant", data.answer, data.tool);
}

document.getElementById("askForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.getElementById("question");
  const question = input.value.trim();
  if (!question) return;
  input.value = "";
  ask(question);
});

document.getElementById("chips").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-q]");
  if (button) ask(button.getAttribute("data-q"));
});
