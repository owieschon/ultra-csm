export function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme");
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  try {
    window.localStorage.setItem("ucsm-theme", next);
  } catch {
    // localStorage unavailable (private mode, etc.) -- theme just won't persist
  }
  return next;
}
