function shouldRefreshHostSeasons() {
  return state.selectedMode === "lobby" && (!state.hostSeasonsLoadedAt || Date.now() - state.hostSeasonsLoadedAt > 15000);
}

function rerenderDashboardInPlace() {
  syncDashboardView(true);
}

function getDashboardViewModel() {
  const status = state.agentStatus || { running: false, status: "Остановлен", state: "stopped", label: "Лаунчер готов", pending_uploads: 0, pending_telemetry: 0, lifecycle: { phase: "stopped" } };
  const live = state.live || {};
  const diagnostics = state.diagnostics || { backend: {}, frontend: {}, auth: {}, cache: { pending_uploads: status.pending_uploads || 0, pending_telemetry: status.pending_telemetry || 0, entries: [], telemetry_entries: [] }, components: {}, recent_events: [], recovery: [] };
  const components = diagnostics.components || {};
  const backendOk = diagnostics.backend?.ok;
  const frontendOk = diagnostics.frontend?.ok;
  const authOk = diagnostics.auth?.ok;
  const selectedHostSeason = getHostSeasonById(state.selectedSeason);
  const startDisabled = (!status.running && state.selectedMode === "lobby" && (!selectedHostSeason || state.hostSeasonsLoading)) || ["booting", "stopping"].includes(status.state);
  const pendingUploads = diagnostics.cache?.pending_uploads ?? status.pending_uploads ?? 0;
  const pendingEntries = diagnostics.cache?.entries || [];
  const pendingTelemetry = diagnostics.cache?.pending_telemetry ?? status.pending_telemetry ?? 0;
  const telemetryEntries = diagnostics.cache?.telemetry_entries || [];
  const telemetryReady = diagnostics.cache?.telemetry_ready_to_flush ?? 0;
  const telemetryBlocked = diagnostics.cache?.telemetry_waiting_for_race_id ?? 0;
  const retryRunning = Boolean(diagnostics.cache?.retry_running);
  const recentEvents = diagnostics.recent_events || [];
  const recovery = diagnostics.recovery || [];
  const lifecycle = status.lifecycle || {};
  const startupIssue = components.startup?.last_error?.message || status.error;
  const headlineIssue = recovery.find(item => item.severity !== "ok");
  const issueCount = recovery.filter(item => item.severity !== "ok").length;

  return {
    authOk,
    backendOk,
    components,
    diagnostics,
    frontendOk,
    headlineIssue,
    issueCount,
    lifecycle,
    live,
    pendingEntries,
    pendingTelemetry,
    pendingUploads,
    recentEvents,
    recovery,
    retryRunning,
    selectedHostSeason,
    startDisabled,
    startupIssue,
    status,
    telemetryBlocked,
    telemetryEntries,
    telemetryReady,
  };
}

function dashboardSignature(value) {
  return JSON.stringify(value ?? null);
}

function componentRenderSignature(component) {
  if (!component) return null;
  return {
    state: component.state,
    message: component.message,
    last_error: component.last_error?.message || null,
  };
}

function replaceDashboardSection(sectionName, html) {
  const section = document.querySelector(`[data-dashboard-section="${sectionName}"]`);
  if (!section) return;

  const scrollTops = {};
  section.querySelectorAll("[data-dashboard-scroll]").forEach(node => {
    scrollTops[node.getAttribute("data-dashboard-scroll")] = node.scrollTop;
  });

  section.innerHTML = html;
  section.querySelectorAll("[data-dashboard-scroll]").forEach(node => {
    const key = node.getAttribute("data-dashboard-scroll");
    if (scrollTops[key] != null) node.scrollTop = scrollTops[key];
  });
}

function getDashboardReadiness(view) {
  if (view.status.state === "error" || view.startupIssue) {
    return {
      tone: "offline",
      label: "Старт заблокирован",
      helper: view.startupIssue || view.status.error || view.status.label || "Агент остановился после ошибки.",
    };
  }

  if (state.selectedMode === "lobby" && !view.selectedHostSeason) {
    return {
      tone: "warn",
      label: "Нужна привязка",
      helper: "Перед запуском host mode нужен явный выбор сезона лобби.",
    };
  }

  if (!view.backendOk) {
    return {
      tone: "warn",
      label: "Backend недоступен",
      helper: view.diagnostics.backend?.message || "Backend сейчас недоступен.",
    };
  }

  if (["error", "unavailable"].includes(view.components.ws?.state) || ["error", "unavailable"].includes(view.components.udp?.state)) {
    return {
      tone: "warn",
      label: "Стек деградирован",
      helper: "WebSocket или UDP сообщили об ошибке. Проверь стек перед стартом.",
    };
  }

  if (view.pendingUploads || view.pendingTelemetry) {
    return {
      tone: "warn",
      label: "Доставка буферизована",
      helper: `Локально сохранено ${view.pendingUploads} гонок и ${view.pendingTelemetry} telemetry-снимков до восстановления цепочки доставки.`,
    };
  }

  if (view.status.running) {
    return {
      tone: "online",
      label: "Агент запущен",
      helper: view.status.label || "Агент запущен и ждёт телеметрию.",
    };
  }

  return {
    tone: "info",
    label: "Готов",
    helper: "Стек готов к запуску из этого окна.",
  };
}

function getDashboardBinding(view) {
  const seasonId = view.status.season_id || state.config?.season_id || "1";
  const binding = state.selectedMode === "lobby"
    ? (view.selectedHostSeason
      ? {
          title: `${view.selectedHostSeason.lobby_name} / ${view.selectedHostSeason.name}`,
          helper: `${translateSeasonStatus(view.selectedHostSeason.status || "active")} · ${view.selectedHostSeason.races_count || 0} гонок проведено`,
        }
      : {
          title: "Хост-сезон не выбран",
          helper: state.hostSeasonsLoading ? "Каталог сезонов лобби загружается." : "Выбери сезон лобби перед запуском host mode.",
        })
    : {
        title: `Личный режим / сезон ${seasonId}`,
        helper: "Локальный режим без привязки к лобби.",
      };

  const session = view.live.active
    ? {
        title: `${view.live.track_name || "Живая сессия"}${view.live.position ? ` · P${view.live.position}` : ""}`,
        helper: [
          view.live.lap ? `круг ${view.live.lap}` : null,
          view.live.best_lap && view.live.best_lap !== "-" ? `лучший ${view.live.best_lap}` : null,
          view.live.weather ? String(view.live.weather) : null,
        ].filter(Boolean).join(" · "),
      }
    : {
        title: view.status.track_name || (view.status.running ? "Ожидание живой сессии" : "Агент не запущен"),
        helper: view.status.running
          ? "Агент уже работает и ждёт поток UDP из F1 25."
          : "Снимок сессии появится после запуска агента.",
      };

  return { binding, session };
}

function getDashboardNextAction(view) {
  if (state.selectedMode === "lobby" && !view.selectedHostSeason) {
    return {
      title: "Выбери сезон лобби",
      copy: "Без привязки к сезону запуск lobby host режима останется заблокирован.",
      primary: { label: "Лобби", variant: "secondary", onclick: "navigate('lobbies')" },
      secondary: { label: "Обновить список", variant: "ghost", onclick: "loadHostSeasons(true)" },
    };
  }

  if (!view.backendOk) {
    return {
      title: "Восстанови backend",
      copy: view.diagnostics.backend?.message || "Launcher не может достучаться до backend.",
      primary: { label: "Настройки", variant: "secondary", onclick: "navigate('settings')" },
      secondary: { label: "Обновить стек", variant: "ghost", onclick: "runDiagnostics()" },
    };
  }

  if (view.startupIssue || view.status.state === "error") {
    return {
      title: "Разбери ошибку запуска",
      copy: view.startupIssue || view.status.error || "Агент остановился после ошибки.",
      primary: { label: "Настройки", variant: "secondary", onclick: "navigate('settings')" },
      secondary: { label: "Папка данных", variant: "ghost", onclick: "openDataFolder()" },
    };
  }

  if (view.pendingUploads || view.pendingTelemetry) {
    return {
      title: "Повтори отложенную доставку",
      copy: `В буфере лежат ${view.pendingUploads} гонок и ${view.pendingTelemetry} telemetry-снимков. После восстановления backend повтори доставку из launcher.`,
      primary: { label: "Повторить доставку", variant: "secondary", onclick: "retryPendingUploads()" },
      secondary: { label: "Папка данных", variant: "ghost", onclick: "openDataFolder()" },
    };
  }

  if (!view.status.running) {
    return {
      title: "Запусти агент",
      copy: state.selectedMode === "lobby"
        ? "После запуска agent привяжется к выбранному сезону и начнёт ждать телеметрию."
        : "Локальный runtime готов. После запуска следи за metrics и журналом событий.",
      primary: { label: "Веб-приложение", variant: "ghost", onclick: "openSite()" },
      secondary: { label: "Папка данных", variant: "ghost", onclick: "openDataFolder()" },
    };
  }

  if (!view.live.active) {
    return {
      title: "Дождись телеметрии",
      copy: "Агент уже работает; открой F1 25 и начни сессию, чтобы заполнить снимок телеметрии.",
      primary: { label: "Оверлей", variant: "secondary", onclick: "openOverlay()" },
      secondary: { label: "Веб-приложение", variant: "ghost", onclick: "openSite()" },
    };
  }

  return {
    title: "Следи за логами и телеметрией",
    copy: "Система в рабочем режиме. Главный сигнал и журнал покажут отклонения без перезагрузки окна.",
    primary: { label: "Оверлей", variant: "ghost", onclick: "openOverlay()" },
    secondary: { label: "Веб-приложение", variant: "ghost", onclick: "openSite()" },
  };
}

function renderEventRow(event) {
  return `<div class="event-item">
    <div class="event-meta">
      <div class="row" style="align-items:center">
        ${pillByTone(severityTone(event.level), translateSeverityLabel(event.level || "info"))}
        <span class="mono subtle">${esc(event.source || "runtime")}</span>
      </div>
      <span class="subtle">${esc(formatRelativeTime(event.at))}</span>
    </div>
    <div class="event-copy">
      <strong>${esc(event.message || "Событие runtime")}</strong>
      ${event.detail ? `<div>${esc(event.detail)}</div>` : ""}
    </div>
  </div>`;
}

function renderRecentEvents(events) {
  if (!events?.length) {
    return renderEmptyState("Событий пока нет", "Журнал заполнится после запуска агента, диагностики и сетевых изменений.");
  }
  return `<div class="event-feed">${events.slice(0, 12).map(renderEventRow).join("")}</div>`;
}

function getDashboardSectionRenderers() {
  return {
    summary: renderDashboardSummarySection,
    control: renderDashboardControlSection,
    metrics: renderDashboardMetricsSection,
    diagnostics: renderDashboardDiagnosticsSection,
    live: renderDashboardLiveSection,
    events: renderDashboardEventsSection,
  };
}

function getDashboardSectionSignatures(view) {
  const { components, diagnostics, lifecycle, live, pendingEntries, pendingTelemetry, pendingUploads, recentEvents, retryRunning, selectedHostSeason, startDisabled, startupIssue, status, telemetryBlocked, telemetryReady } = view;
  return {
    summary: dashboardSignature({
      live: {
        active: live.active,
        best_lap: live.best_lap,
        lap: live.lap,
        position: live.position,
        track_name: live.track_name,
        weather: live.weather,
      },
      selectedHostSeason,
      selectedMode: state.selectedMode,
      selectedSeason: state.selectedSeason,
      hostSeasonsLoading: state.hostSeasonsLoading,
      pendingTelemetry,
      pendingUploads,
      retryRunning,
      startDisabled,
      startupIssue,
      status: {
        label: status.label,
        running: status.running,
        season_id: status.season_id,
        state: status.state,
        status: status.status,
        track_name: status.track_name,
        uptime_s: status.uptime_s,
      },
      lifecyclePhase: lifecycle.phase,
      udp_port: state.config?.udp_port,
      data_dir: state.config?.data_dir,
      backend: diagnostics.backend,
      ws: componentRenderSignature(components.ws),
      udp: componentRenderSignature(components.udp),
    }),
    control: dashboardSignature({
      backend: diagnostics.backend,
      cache: diagnostics.cache,
      headlineIssue: view.headlineIssue,
      issueCount: view.issueCount,
      live: { active: live.active },
      pendingTelemetry,
      selectedHostSeason,
      selectedMode: state.selectedMode,
      startDisabled,
      startupIssue,
      status: {
        label: status.label,
        running: status.running,
        state: status.state,
      },
      components: {
        startup: componentRenderSignature(components.startup),
        udp: componentRenderSignature(components.udp),
        telemetry: componentRenderSignature(components.telemetry),
        upload: componentRenderSignature(components.upload),
        ws: componentRenderSignature(components.ws),
      },
    }),
    metrics: dashboardSignature({
      backend: diagnostics.backend,
      live: {
        active: live.active,
        best_lap: live.best_lap,
        position: live.position,
        track_name: live.track_name,
      },
      pendingTelemetry,
      pendingUploads,
      retryRunning,
      status: {
        label: status.label,
        state: status.state,
        status: status.status,
      },
    }),
    diagnostics: dashboardSignature({
      auth: diagnostics.auth,
      backend: diagnostics.backend,
      frontend: diagnostics.frontend,
      components: {
        startup: componentRenderSignature(components.startup),
        ws: componentRenderSignature(components.ws),
        udp: componentRenderSignature(components.udp),
        overlay: componentRenderSignature(components.overlay),
        upload: componentRenderSignature(components.upload),
        telemetry: componentRenderSignature(components.telemetry),
      },
      data_dir: state.config?.data_dir,
      lifecyclePhase: lifecycle.phase,
      pendingEntries,
      pendingTelemetry,
      pendingUploads,
      retryRunning,
      startupIssue,
      telemetryBlocked,
      telemetryReady,
      udp_port: state.config?.udp_port,
    }),
    live: dashboardSignature(live),
    events: dashboardSignature(recentEvents.slice(0, 12)),
  };
}

function syncDashboardView(force = false) {
  if (state.page !== "dashboard") return;
  const root = document.getElementById("app-root");
  const page = document.querySelector(".page-dashboard");
  if (!root) return;
  if (!page) {
    root.innerHTML = layout(renderDashboard());
    return;
  }

  const view = getDashboardViewModel();
  const next = getDashboardSectionSignatures(view);
  const prev = state.dashboardSectionSignatures || {};
  const renderers = getDashboardSectionRenderers();

  Object.entries(renderers).forEach(([name, renderSection]) => {
    if (force || next[name] !== prev[name]) {
      replaceDashboardSection(name, renderSection(view));
    }
  });

  state.dashboardSectionSignatures = next;
}

function renderDashboardSummarySection(view) {
  const readiness = getDashboardReadiness(view);
  const binding = getDashboardBinding(view);
  const phaseTone = componentTone(view.lifecycle.phase || view.status.state);
  const phaseMeta = [
    view.status.running ? `uptime ${formatUptime(view.status.uptime_s)}` : "агент остановлен",
    view.status.track_name || null,
  ].filter(Boolean).join(" · ");

  return `<div class="dashboard-summary-head">
      <div>
        <div class="eyebrow">Race Control</div>
        <h2 class="dashboard-title">Пульт оператора</h2>
        <p class="dashboard-summary-copy clamp-2">${esc(view.status.label || "Лаунчер готов")}. ${esc(readiness.helper)}</p>
      </div>
      <div class="dashboard-summary-actions">
        ${renderButton({
          label: view.status.running ? "Остановить агент" : "Запустить агент",
          variant: view.status.running ? "danger" : "primary",
          onclick: "toggleAgent()",
          disabled: view.startDisabled,
          className: "dashboard-primary-action",
        })}
        <div class="dashboard-chip-row">
          ${pillByTone(readiness.tone, readiness.label)}
          ${pillByTone(phaseTone, `Фаза ${translateComponentState(view.lifecycle.phase || view.status.state)}`)}
        </div>
      </div>
    </div>
    <div class="dashboard-summary-layout">
      <div class="dashboard-command-card">
        <div>
          <div class="meta-label">Текущая фаза</div>
          <strong class="dashboard-phase-value">${esc(view.status.status)}</strong>
          <p class="dashboard-phase-copy clamp-2">${esc(phaseMeta || "Ожидание запуска")}</p>
        </div>
        <div class="dashboard-context-item">
          <span class="meta-label">Текущая связка</span>
          <strong class="clamp-2">${esc(binding.binding.title)}</strong>
          <p class="clamp-2">${esc([binding.binding.helper, binding.session.title, binding.session.helper].filter(Boolean).join(" · "))}</p>
        </div>
      </div>
      <div class="dashboard-mode-card">
        <div>
          <div class="meta-label">Режим</div>
          <div class="dashboard-mode-copy clamp-2">${state.selectedMode === "lobby"
            ? (view.selectedHostSeason ? `Хост лобби · ${binding.binding.title}` : "Для режима хоста нужен выбранный сезон лобби.")
            : `Личный режим · сезон ${view.status.season_id || state.config?.season_id || "1"}`}</div>
        </div>
        ${renderModeToggle()}
        <div class="field dashboard-host-field ${state.selectedMode === "lobby" ? "" : "is-hidden"}">
          <label>Привязка к сезону</label>
          <select id="dashboard-season-select" onchange="pickHostSeason(this.value)">
            ${renderHostSeasonOptions()}
          </select>
        </div>
      </div>
    </div>`;
}

function renderDashboardControlSection(view) {
  const readiness = getDashboardReadiness(view);
  const nextAction = getDashboardNextAction(view);
  const headline = view.headlineIssue;
  const headlineTone = headline ? String(headline.severity || "warn") : "ok";
  const issueLabel = view.issueCount === 1 ? "проблема" : view.issueCount < 5 ? "проблемы" : "проблем";
  const deliveryCount = view.pendingUploads + view.pendingTelemetry;
  const deliveryHelper = deliveryCount
    ? (view.retryRunning
      ? "Повтор уже выполняется из launcher."
      : [view.pendingUploads ? `${view.pendingUploads} загрузок` : null, view.pendingTelemetry ? `${view.pendingTelemetry} telemetry` : null].filter(Boolean).join(" · "))
    : (view.components.upload?.message || "Буфер доставки чистый.");

  return `${renderPanelHeader("Операции", "Состояние стека", "Главный сигнал, состояние сервисов и ближайший шаг.", pillByTone(readiness.tone, readiness.label))}
    <div class="dashboard-control-body">
      <div class="dashboard-headline-card ${headlineTone}">
        <div class="meta-label">Главный сигнал</div>
        <div class="dashboard-inline-head">
          <strong class="clamp-2">${esc(headline ? headline.title : "Система готова")}</strong>
          ${headline
            ? pillByTone(severityTone(headline.severity || "warn"), `${view.issueCount} ${issueLabel}`)
            : pillByTone("online", "стабильно")}
        </div>
        <p class="clamp-3">${esc(headline ? headline.summary : "Критических блокеров для запуска, телеметрии и ручного recovery сейчас не видно.")}</p>
      </div>
      <div class="dashboard-next-card">
        <div class="meta-label">Следующее действие</div>
        <strong>${esc(nextAction.title)}</strong>
        ${deliveryCount && !view.status.running ? `<p class="clamp-1">${esc(deliveryHelper)}</p>` : ""}
      </div>
      <div class="dashboard-panel-actions">
        ${nextAction.primary ? renderButton(nextAction.primary) : ""}
        ${nextAction.secondary ? renderButton(nextAction.secondary) : ""}
      </div>
    </div>`;
}

function renderDashboardMetricsSection(view) {
  const phaseTone = view.status.state === "error"
    ? "offline"
    : ["booting", "stopping"].includes(view.status.state)
      ? "warn"
      : view.status.running
        ? "online"
        : "info";
  const latencyTone = !view.backendOk ? "offline" : (view.diagnostics.backend?.latency_ms != null && view.diagnostics.backend.latency_ms > 250 ? "warn" : "info");
  const latencyValue = view.diagnostics.backend?.latency_ms != null ? `${view.diagnostics.backend.latency_ms} мс` : (view.backendOk ? "--" : "offline");
  const liveValue = view.live.position ? `P${view.live.position}` : (view.live.active ? "идёт" : "--");
  const liveHelper = view.live.active
    ? [view.live.track_name || null, view.live.best_lap && view.live.best_lap !== "-" ? `лучший ${view.live.best_lap}` : null].filter(Boolean).join(" · ")
    : "Живая сессия ещё не обнаружена";

  return [
    renderMetricCard("Фаза агента", view.status.status, view.status.label || "Состояние runtime агента", phaseTone),
    renderMetricCard(
      "Буфер доставки",
      String(view.pendingUploads + view.pendingTelemetry),
      view.retryRunning
        ? "Повтор уже идёт."
        : ((view.pendingUploads || view.pendingTelemetry)
          ? `гонки ${view.pendingUploads} · telemetry ${view.pendingTelemetry}`
          : "Очереди чистые."),
      (view.pendingUploads || view.pendingTelemetry) ? "warn" : "online"
    ),
    renderMetricCard("Задержка backend", latencyValue, view.diagnostics.backend?.message || "Проверка backend ещё не выполнена", latencyTone),
    renderMetricCard("Снимок сессии", liveValue, liveHelper, view.live.active ? "online" : "info"),
  ].join("");
}

function renderDashboardDiagnosticsSection(view) {
  const readiness = getDashboardReadiness(view);
  const authPill = view.authOk
    ? pillByTone("online", "активна")
    : (view.diagnostics.auth?.signed_in ? pillByTone("warn", "ошибка") : pillByTone("info", "не выполнен"));
  const rows = [
    renderDiagnosticRow("Backend", statusPill(Boolean(view.backendOk), view.backendOk ? "доступен" : "недоступен", !view.backendOk), view.diagnostics.backend?.message || "Статус backend не проверен."),
    renderDiagnosticRow("Frontend", statusPill(Boolean(view.frontendOk), view.frontendOk ? "доступен" : "недоступен", !view.frontendOk), view.diagnostics.frontend?.message || "Статус frontend не проверен."),
    renderDiagnosticRow("Сессия авторизации", authPill, view.diagnostics.auth?.message || "Вход в launcher не выполнен."),
    renderDiagnosticRow("Startup", componentStatePill(view.components.startup, view.lifecycle.phase || view.status.state), `${view.components.startup?.message || view.status.label || "Launcher готов"}${view.startupIssue ? ` · ${view.startupIssue}` : ""}`),
    renderDiagnosticRow("WebSocket", componentStatePill(view.components.ws), `${view.components.ws?.message || "Ожидание websocket активности"}${view.components.ws?.last_error?.message ? ` · ${view.components.ws.last_error.message}` : ""}`),
    renderDiagnosticRow("UDP поток", componentStatePill(view.components.udp), `${view.components.udp?.message || `Порт ${state.config?.udp_port || "20777"}`}${view.components.udp?.last_error?.message ? ` · ${view.components.udp.last_error.message}` : ""}`),
    renderDiagnosticRow("Overlay", componentStatePill(view.components.overlay), `${view.components.overlay?.message || "Overlay в ожидании"}${view.components.overlay?.last_error?.message ? ` · ${view.components.overlay.last_error.message}` : ""}`),
    renderDiagnosticRow("Очередь загрузок", componentStatePill(view.components.upload), `${view.components.upload?.message || "Очередь загрузок пустая"}${view.components.upload?.last_error?.message ? ` · ${view.components.upload.last_error.message}` : ""}`),
    renderDiagnosticRow("Telemetry flush", componentStatePill(view.components.telemetry), `${view.components.telemetry?.message || "Очередь telemetry flush пустая"}${view.components.telemetry?.last_error?.message ? ` · ${view.components.telemetry.last_error.message}` : ""}`),
    renderDiagnosticRow("Папка данных", pillByTone("info", "local"), state.config?.data_dir || "Путь к папке данных не задан."),
  ].join("");

  return `${renderPanelHeader("Система", "Диагностика", "Проверка подключений и runtime-компонентов.", pillByTone(readiness.tone, readiness.label))}
    <div class="dashboard-panel-body" data-dashboard-scroll="diagnostics-body">${rows}</div>
    <div class="dashboard-panel-actions">
      ${renderButton({ label: "Папка данных", variant: "ghost", onclick: "openDataFolder()" })}
      ${renderButton({ label: "Веб-приложение", variant: "ghost", onclick: "openSite()" })}
      ${renderButton({ label: "Настройки", variant: "ghost", onclick: "navigate('settings')" })}
    </div>`;
}

function renderDashboardLiveSection(view) {
  const live = view.live || {};
  const aside = live.active ? pillByTone("online", "активно") : pillByTone("info", "ожидание");

  if (!live.active) {
    return `${renderPanelHeader("Телеметрия", "Снимок телеметрии", "Короткий срез активной сессии без отдельного модуля.", aside)}
      <div class="dashboard-panel-body" data-dashboard-scroll="live-body">
        ${renderEmptyState("Нет живой телеметрии", view.status.running ? "Агент запущен и ждёт поток UDP из F1 25." : "Запусти агент, затем открой сессию в F1 25.")}
      </div>`;
  }

  const cards = [
    renderTelemetryCard("Трасса", live.track_name || "--", live.weather ? `погода ${live.weather}` : "ожидание погодных данных"),
    renderTelemetryCard("Позиция / круг", `${live.position ? `P${live.position}` : "--"} · ${live.lap || "--"}`, live.best_lap && live.best_lap !== "-" ? `лучший ${live.best_lap}` : "лучший круг пока не получен"),
    renderTelemetryCard("Последний / лучший", `${live.last_lap || "-"} · ${live.best_lap || "-"}`, "время по текущему пакету"),
    renderTelemetryCard("Скорость / передача", `${live.speed != null ? `${live.speed} км/ч` : "--"} · ${live.gear ?? "--"}`, "текущее состояние машины"),
    renderTelemetryCard("Газ / тормоз", `${live.throttle != null ? `${live.throttle}%` : "--"} · ${live.brake != null ? `${live.brake}%` : "--"}`, "положение педалей из входящего пакета"),
    renderTelemetryCard("Шины", live.tyre || "--", live.tyre_wear_avg != null ? `средний износ ${live.tyre_wear_avg}%` : "данные об износе ещё не получены"),
    renderTelemetryCard("Топливо", live.fuel_laps != null ? `${live.fuel_laps} круга` : "--", "оценка остатка по кругам"),
    renderTelemetryCard("Состояние", translateComponentState(view.status.state || "waiting"), view.status.label || "Агент ждёт смены состояния"),
  ].join("");

  return `${renderPanelHeader("Телеметрия", "Снимок телеметрии", "Текущий срез пилота и машины.", aside)}
    <div class="dashboard-panel-body" data-dashboard-scroll="live-body">
      <div class="telemetry-grid">${cards}</div>
    </div>`;
}

function renderDashboardEventsSection(view) {
  const aside = view.recentEvents[0] ? `<span class="subtle">последнее ${esc(formatRelativeTime(view.recentEvents[0].at))}</span>` : "";
  return `${renderPanelHeader("Журнал", "События", "Последние события runtime и сети.", aside)}
    <div class="dashboard-panel-body" data-dashboard-scroll="events-body">
      ${renderRecentEvents(view.recentEvents)}
    </div>`;
}

function renderDashboard() {
  const view = getDashboardViewModel();
  state.dashboardSectionSignatures = getDashboardSectionSignatures(view);
  return `<div class="page page-dashboard">
    <div class="dashboard-top">
      <section class="shell-card dashboard-card dashboard-summary" data-dashboard-section="summary">${renderDashboardSummarySection(view)}</section>
      <section class="shell-card dashboard-card dashboard-control" data-dashboard-section="control">${renderDashboardControlSection(view)}</section>
    </div>
    <div class="dashboard-metrics" data-dashboard-section="metrics">${renderDashboardMetricsSection(view)}</div>
    <div class="dashboard-bottom">
      <section class="panel dashboard-panel" data-dashboard-section="diagnostics">${renderDashboardDiagnosticsSection(view)}</section>
      <section class="panel dashboard-panel dashboard-panel-no-footer" data-dashboard-section="live">${renderDashboardLiveSection(view)}</section>
      <section class="panel dashboard-panel dashboard-panel-no-footer dashboard-events-panel" data-dashboard-section="events">${renderDashboardEventsSection(view)}</section>
    </div>
  </div>`;
}

async function loadDashboard() {
  await Promise.all([
    refreshRuntime(),
    shouldRefreshHostSeasons() ? loadHostSeasons(false) : Promise.resolve(state.hostSeasons),
  ]);
  if (state.page !== "dashboard") return;
  syncDashboardView(true);
}

function setMode(mode) {
  state.selectedMode = mode;
  syncDashboardView(true);
  if (mode === "lobby" && shouldRefreshHostSeasons()) {
    state.hostSeasonsLoading = true;
    syncDashboardView(true);
    queueMicrotask(() => loadHostSeasons(true));
  }
}

async function runDiagnostics(rerender = true) {
  await refreshRuntime();
  if (!rerender) return;
  if (state.page === "dashboard") {
    syncDashboardView(true);
    return;
  }
  render();
}

async function retryPendingUploads() {
  try {
    const result = unwrap(await api("retry_pending_uploads_now"), "Не удалось повторить отложенные загрузки");
    toast(result.started ? "Запущен повтор отложенной доставки" : "Нет отложенной доставки для повтора", result.started ? "info" : "success");
    await refreshRuntime();
    if (state.page === "dashboard") {
      syncDashboardView(true);
    } else {
      render();
    }
  } catch (error) {
    toast(error.message || "Не удалось повторить отложенные загрузки", "error");
  }
}
