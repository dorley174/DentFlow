/* DentFlow embeddable widget. Usage: <script src="https://YOUR-DOMAIN/widget.js" data-clinic="your-slug" defer></script> */
(() => {
  const script = document.currentScript;
  if (!script || !script.dataset.clinic) return;
  const clinic = script.dataset.clinic;
  if (!/^[a-z0-9][a-z0-9-]{0,79}$/.test(clinic)) return;
  const origin = new URL(script.src).origin;
  const host = document.createElement("div");
  const shadow = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent =
    ":host{all:initial}button{position:fixed;right:24px;bottom:24px;z-index:2147483000;background:#087f8c;color:#fff;border:0;border-radius:50px;padding:16px 22px;font:600 15px system-ui;cursor:pointer;box-shadow:0 8px 30px #122b3926}iframe{display:none;position:fixed;right:24px;bottom:90px;width:380px;height:min(640px,calc(100dvh - 120px));border:1px solid #dbe8e6;border-radius:20px;background:white;z-index:2147483000;box-shadow:0 15px 60px #122b3930}@media(max-width:480px){iframe{right:10px;width:calc(100vw - 20px)}button{right:12px;bottom:12px}}";
  const button = document.createElement("button");
  button.textContent = "Поможем с записью";
  button.type = "button";
  button.setAttribute("aria-expanded", "false");
  const frame = document.createElement("iframe");
  frame.title = "Чат с клиникой";
  frame.src = origin + "/widget/" + encodeURIComponent(clinic);
  frame.referrerPolicy = "strict-origin-when-cross-origin";
  let open = false;
  button.addEventListener("click", () => {
    open = !open;
    frame.style.display = open ? "block" : "none";
    button.textContent = open ? "Закрыть чат" : "Поможем с записью";
    button.setAttribute("aria-expanded", String(open));
  });
  shadow.append(style, frame, button);
  document.body.append(host);
})();
