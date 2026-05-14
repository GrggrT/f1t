function navItem(page, title, subtitle) {
  return `<button class="nav-item ${state.page === page ? "active" : ""}" onclick="navigate('${page}')">
    <div class="nav-copy">
      <div class="nav-title">${esc(title)}</div>
      <small>${esc(subtitle)}</small>
    </div>
    <span class="nav-state">${state.page === page ? "•" : ""}</span>
  </button>`;
}

function layout(content, sidebar = true) {
  const workspaceClass = ["workspace", state.page === "dashboard" ? "workspace-dashboard" : "", !sidebar ? "no-sidebar" : ""].filter(Boolean).join(" ");
  if (!sidebar) {
    return `<main class="${workspaceClass}">${content}</main>`;
  }

  const user = state.user || {};
  return `<div class="app">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-top">
          <div class="badge-logo">F1</div>
          <div>
            <h1>F1 League Launcher</h1>
            <p>Агент, лобби и восстановление в одном окне.</p>
          </div>
        </div>
      </div>
      <nav class="nav">
        ${navItem("dashboard", "Race Control", "агент и телеметрия")}
        ${navItem("lobbies", "Lobbies", "сезоны и доступ")}
        ${navItem("profile", "Profile", "статистика и история")}
        ${navItem("engineer", "Race Engineer", "чат по сессии")}
        ${navItem("settings", "Settings", "подключения и оверлей")}
      </nav>
      <div class="sidebar-spacer"></div>
      <div class="sidebar-tools">
        <button class="utility-btn" onclick="openSite()">Веб-приложение</button>
        <button class="utility-btn" onclick="openDataFolder()">Папка данных</button>
      </div>
      <div class="user-box">
        <div class="user-head">
          <div class="avatar">${initials(user.name)}</div>
          <div class="user-meta">
            <strong>${esc(user.name || "Оператор")}</strong>
            <span>${esc(user.email || "Вход не выполнен")}</span>
          </div>
        </div>
        <div class="user-actions">
          ${renderButton({ label: "Выйти", variant: "ghost", onclick: "logoutUser()", className: "btn-wide" })}
        </div>
      </div>
    </aside>
    <main class="${workspaceClass}">${content}</main>
  </div>`;
}
