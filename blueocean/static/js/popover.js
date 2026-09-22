/* 팝오버 구현 메모(§3.9.3) 대응: data-bs-trigger 대신 직접 구현한다.
 * 언제나 팝오버는 1개만 열리고, 바깥 클릭·Esc·같은 버튼 재클릭으로 닫힌다. */
window.BOFPopover = (function () {
  "use strict";

  let current = null; // { key, el }

  function close() {
    if (current) {
      current.el.remove();
      current = null;
    }
  }

  function isOpen(key) {
    return !!current && current.key === key;
  }

  function toggle(anchorEl, key, buildContentEl) {
    if (isOpen(key)) {
      close();
      return;
    }
    close();

    const content = buildContentEl();
    const pop = document.createElement("div");
    pop.className = "bof-popover";
    pop.setAttribute("role", "dialog");
    pop.appendChild(content);
    document.body.appendChild(pop);

    const rect = anchorEl.getBoundingClientRect();
    const top = window.scrollY + rect.bottom + 6;
    let left = window.scrollX + rect.left;
    const maxLeft = window.scrollX + document.documentElement.clientWidth - pop.offsetWidth - 8;
    left = Math.max(8, Math.min(left, maxLeft));
    pop.style.top = top + "px";
    pop.style.left = left + "px";

    current = { key, el: pop };
  }

  document.addEventListener("click", (e) => {
    if (!current) return;
    const insidePopover = current.el.contains(e.target);
    const isTrigger = !!e.target.closest("[data-popover-trigger]");
    if (!insidePopover && !isTrigger) close();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });

  window.addEventListener("scroll", () => close(), true);

  return { toggle, close, isOpen };
})();
