import React, { useEffect, useMemo, useState } from "react";

import { api } from "./api.js";

import logoFull from "./assets/logo_full.png";

import logoIcon from "./assets/logo_icon.png";



const STATUSES = ["PENDENTE", "EM_ANDAMENTO", "CONCLUIDA", "ENVIADA", "DISPENSADA"];

const STATUS_LABELS = {

  PENDENTE: "Pendente",

  EM_ANDAMENTO: "Em andamento",

  CONCLUIDA: "Conclu?da",

  ENVIADA: "Enviada",

  DISPENSADA: "Dispensada",

};

const STATUS_COLORS = {

  PENDENTE: "#ef4444",

  EM_ANDAMENTO: "#f59e0b",

  CONCLUIDA: "#22c55e",

  ENVIADA: "#3b82f6",

  DISPENSADA: "#94a3b8",

};

const ORGAO_LABELS = { MUN: "Municipal", EST: "Estadual", FED: "Federal" };

const REGIMES = ["Todas", "Simples Nacional", "Lucro Presumido", "Lucro Real"];
const NOTIFICATION_POLL_MS = 3000;
const AUTH_STORAGE_KEY = "fiscalhub.auth.user";
const AUTH_REMEMBER_KEY = "fiscalhub.auth.remember";
const UI_ACTIVE_KEY = "fiscalhub.ui.active";
const UI_COMPANY_KEY = "fiscalhub.ui.company";

function readStoredUser() {
  const local = localStorage.getItem(AUTH_STORAGE_KEY);
  const session = sessionStorage.getItem(AUTH_STORAGE_KEY);
  const raw = local || session;
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch (_) {
    return null;
  }
}

function readStoredActive() {
  return localStorage.getItem(UI_ACTIVE_KEY) || sessionStorage.getItem(UI_ACTIVE_KEY) || "home";
}

function readStoredCompanyId() {
  const raw = localStorage.getItem(UI_COMPANY_KEY) || sessionStorage.getItem(UI_COMPANY_KEY);
  const id = Number(raw);
  return Number.isInteger(id) && id > 0 ? id : null;
}



function fmtComp(yyyymm) {

  if (!yyyymm) return "-";

  const s = String(yyyymm);

  if (s.length === 6) return `${s.slice(4, 6)}/${s.slice(0, 4)}`;

  return s;

}



function fmtDate(value) {

  if (!value) return "-";

  const s = String(value);

  if (s.includes("-")) {

    const parts = s.split("-");

    if (parts.length >= 3) {

      const [y, m, d] = parts;

      return `${d}/${m}/${y}`;

    }

  }

  return s;

}

function fmtDateTime(value) {
  if (!value) return "-";
  const raw = String(value).trim();
  const isoLike = raw.includes("T") ? raw : raw.replace(" ", "T");
  const withZone =
    /Z$|[+\-]\d{2}:\d{2}$/.test(isoLike) ? isoLike : `${isoLike}Z`;
  const dt = new Date(withZone);
  if (Number.isNaN(dt.getTime())) return raw;
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: "America/Sao_Paulo",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(dt);
}

function notificationTaskId(notification) {
  if (!notification) return null;
  const type = String(notification.type || "").toLowerCase();
  const refId = Number(notification.ref_id);
  if (type === "inconsistency" && Number.isInteger(refId) && refId > 0) return refId;
  const msg = String(notification.message || "");
  const m = msg.match(/\(id\s*(\d+)\)/i) || msg.match(/tarefa\s*(\d+)/i);
  if (m) return Number(m[1]);
  if (Number.isInteger(refId) && refId > 0) return refId;
  return null;
}

function sortCommentsNewest(items) {
  return (Array.isArray(items) ? items : [])
    .slice()
    .sort((a, b) => String(b?.created_at || "").localeCompare(String(a?.created_at || "")));
}



function parseCompLabel(label) {

  const s = (label || "").trim();

  if (!s) return null;

  const m = s.match(/^(0[1-9]|1[0-2])\/(\d{4})$/);

  if (!m) return null;

  return `${m[2]}${m[1]}`;

}



function onlyDigits(s) {

  return (s || "").replace(/\D/g, "");

}



function formatCnpj(s) {

  const d = onlyDigits(s).slice(0, 14);

  if (!d) return "";

  const p1 = d.slice(0, 2);

  const p2 = d.slice(2, 5);

  const p3 = d.slice(5, 8);

  const p4 = d.slice(8, 12);

  const p5 = d.slice(12, 14);

  let out = p1;

  if (p2) out += `.${p2}`;

  if (p3) out += `.${p3}`;

  if (p4) out += `/${p4}`;

  if (p5) out += `-${p5}`;

  return out;

}

function formatCompetenciaInput(value) {
  const digits = onlyDigits(value).slice(0, 6);
  if (!digits) return "";
  if (digits.length <= 2) return digits;
  return `${digits.slice(0, 2)}/${digits.slice(2)}`;
}

function normalizeObservacoes(obs) {
  if (Array.isArray(obs)) return obs;
  if (!obs) return [];
  return [String(obs)];
}

function obsEqual(a, b) {
  return JSON.stringify(normalizeObservacoes(a)) === JSON.stringify(normalizeObservacoes(b));
}



function parseCompetencia(yyyymm) {

  if (!yyyymm) return null;

  const s = String(yyyymm);

  if (s.length !== 6) return null;

  const year = Number(s.slice(0, 4));

  const month = Number(s.slice(4, 6));

  if (!year || !month) return null;

  return { year, month };

}



function inScope(yyyymm, scope) {

  if (!scope || !scope.year) return true;

  const parsed = parseCompetencia(yyyymm);

  if (!parsed) return false;

  if (parsed.year !== scope.year) return false;

  if (scope.month) return parsed.month === scope.month;

  if (!scope.period || scope.period === "ANUAL") return true;

  const quarterMap = {

    T1: [1, 2, 3],

    T2: [4, 5, 6],

    T3: [7, 8, 9],

    T4: [10, 11, 12],

  };

  const months = quarterMap[scope.period] || [];

  return months.includes(parsed.month);

}



function scopeLabel(scope) {

  if (!scope || !scope.year) return "Todas competências";

  if (scope.month) return `${String(scope.month).padStart(2, "0")}/${scope.year}`;

  if (!scope.period || scope.period === "ANUAL") return `Anual/${scope.year}`;

  return `${scope.period}/${scope.year}`;

}



function Sidebar({ active, onNavigate, collapsed, onToggle, userRole, onLogout }) {

  const showCompanies = userRole === "admin" || userRole === "manager";

  return (

    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>

        <div className="logo-row">

          <img

            className={`logo-img ${collapsed ? "icon" : "full"}`}

            src={collapsed ? logoIcon : logoFull}

            alt="41 Fiscal"

          />

        <button className="collapse" onClick={onToggle} title={collapsed ? "Expandir" : "Recolher"}>
          {collapsed ? ">" : "<"}
        </button>

      </div>

      <nav>

        <button className={active === "home" ? "active" : ""} onClick={() => onNavigate("home")}>

          Home

        </button>

        {showCompanies ? (

          <button className={active === "companies" ? "active" : ""} onClick={() => onNavigate("companies")}>

            Empresas

          </button>

        ) : null}

        <button className={active === "reports" ? "active" : ""} onClick={() => onNavigate("reports")}>

          Relatórios

        </button>

        <button className={active === "settings" ? "active" : ""} onClick={() => onNavigate("settings")}>

          Configurações

        </button>

      </nav>

      <button className="logout-btn" onClick={onLogout} title="Sair">
        <svg className="logout-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M15 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h8" />
          <path d="M10 12h11" />
          <path d="m17 7 5 5-5 5" />
        </svg>
        <span className="logout-label">Sair</span>
      </button>

    </aside>

  );

}



function Login({ onSelect }) {

  const [name, setName] = useState("");

  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(() => localStorage.getItem(AUTH_REMEMBER_KEY) === "1");

  const [error, setError] = useState("");



  const enter = () => {

    setError("");

    api

      .login(name.trim(), password)

      .then((logged) => onSelect(logged, remember))

      .catch(() => setError("Senha inválida"));

  };



  return (

    <div className="login">

      <div className="card">

        <div className="login-logo">

          <img src={logoFull} alt="41 Fiscal" />

        </div>

        <h2>Login</h2>

        <input

          placeholder={"Usuário"}

          value={name}

          onChange={(e) => setName(e.target.value)}

        />

        <input

          type="password"

          placeholder="Senha"

          value={password}

          onChange={(e) => setPassword(e.target.value)}

        />
        <label className="remember-row">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
          />
          <span>Lembrar login</span>
        </label>

        {error ? <div className="muted small">{error}</div> : null}

        <button className="primary" onClick={enter} disabled={!name.trim() || !password}>

          Entrar

        </button>

      </div>

    </div>

  );

}




function HomePage({
  userId,
  donutScope,
  onDonutScopeChange,
  companyScope,
  onCompanyScopeChange,
  onGoCompanies,
  onOpenTaskFromNotification,
  refreshTick,
}) {
  const [tasks, setTasks] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifFilter, setNotifFilter] = useState("UNREAD");
  const initialScope = donutScope?.year && donutScope?.month ? donutScope : companyScope;
  const [companyComp, setCompanyComp] = useState(
    initialScope?.year && initialScope?.month
      ? `${String(initialScope.month).padStart(2, "0")}/${initialScope.year}`
      : ""
  );

  useEffect(() => {
    api
      .listTasks({ user_id: userId })
      .then(setTasks)
      .catch(() => setTasks([]));
  }, [userId, refreshTick]);

  useEffect(() => {
    let alive = true;
    const loadNotifications = () => {
      api
        .listNotifications(userId, false)
        .then((rows) => {
          if (!alive) return;
          setNotifications(Array.isArray(rows) ? rows : []);
        })
        .catch(() => {
          if (!alive) return;
          setNotifications([]);
        });
    };
    loadNotifications();
    const timer = setInterval(loadNotifications, NOTIFICATION_POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [userId, refreshTick]);

  useEffect(() => {
    const syncScope = donutScope?.year && donutScope?.month ? donutScope : companyScope;
    setCompanyComp(
      syncScope?.year && syncScope?.month
        ? `${String(syncScope.month).padStart(2, "0")}/${syncScope.year}`
        : ""
    );
  }, [donutScope?.year, donutScope?.month, companyScope?.year, companyScope?.month]);

  const activeHomeScope = useMemo(() => {
    if (donutScope?.year && donutScope?.month) {
      return { year: donutScope.year, month: donutScope.month };
    }
    return null;
  }, [donutScope?.year, donutScope?.month]);

  const scopedTasks = useMemo(() => {
    if (!activeHomeScope) return tasks;
    return tasks.filter((t) => inScope(t.competencia, activeHomeScope));
  }, [tasks, activeHomeScope]);

  const counts = useMemo(() => {
    const out = {};
    STATUSES.forEach((s) => (out[s] = 0));
    scopedTasks.forEach((t) => {
      out[t.status] = (out[t.status] || 0) + 1;
    });
    return out;
  }, [scopedTasks]);

  const total = STATUSES.reduce((acc, s) => acc + (counts[s] || 0), 0);
  const segments = STATUSES.map((s) => ({
    key: s,
    value: counts[s] || 0,
    color: STATUS_COLORS[s],
  })).filter((x) => x.value > 0);

  const vencimentos = useMemo(() => {
    const withDate = (scopedTasks || []).filter((t) => t.vencimento);
    return withDate
      .slice()
      .sort((a, b) => String(a.vencimento).localeCompare(String(b.vencimento)));
  }, [scopedTasks]);

  const todayKey = new Date().toISOString().slice(0, 10);
  const overdue = vencimentos.filter(
    (t) =>
      String(t.vencimento) < todayKey &&
      !["CONCLUIDA", "ENVIADA", "DISPENSADA"].includes(t.status)
  );
  const unreadNotifications = notifications.filter((n) => !n.is_read);
  const isResolvedNotification = (n) =>
    (String(n?.type || "").toLowerCase() === "resolved" && Boolean(n?.is_read)) ||
    (String(n?.type || "").toLowerCase() === "inconsistency" && Boolean(n?.is_read));
  const visibleNotifications = useMemo(() => {
    if (notifFilter === "UNREAD") return notifications.filter((n) => !n.is_read && !isResolvedNotification(n));
    if (notifFilter === "READ") return notifications.filter((n) => n.is_read && !isResolvedNotification(n));
    if (notifFilter === "RESOLVED") return notifications.filter((n) => isResolvedNotification(n));
    return notifications;
  }, [notifications, notifFilter]);
  const tasksById = useMemo(() => {
    const m = new Map();
    tasks.forEach((t) => m.set(Number(t.id), t));
    return m;
  }, [tasks]);

  const openFromNotification = async (n) => {
    if (!n.is_read) {
      try {
        await api.markNotificationRead(n.id, userId);
      } catch (_) {}
      setNotifications((prev) => prev.map((item) => (item.id === n.id ? { ...item, is_read: true } : item)));
    }
    const taskId = notificationTaskId(n);
    const task = taskId ? tasksById.get(Number(taskId)) : null;
    if (!task || !onOpenTaskFromNotification) return;
    onOpenTaskFromNotification(task);
    setShowNotifications(false);
  };

  const onCompanyCompChange = (value) => {
    const digits = String(value || "").replace(/\D/g, "").slice(0, 6);
    if (!digits) {
      setCompanyComp("");
      onDonutScopeChange(null);
      onCompanyScopeChange(null);
      return;
    }
    if (digits.length <= 2) {
      setCompanyComp(digits);
      return;
    }
    const formatted = `${digits.slice(0, 2)}/${digits.slice(2)}`;
    setCompanyComp(formatted);
    const comp = parseCompLabel(formatted);
    if (!comp) return;
    const parsed = parseCompetencia(comp);
    const nextScope = parsed ? { year: parsed.year, month: parsed.month } : null;
    onDonutScopeChange(nextScope);
    onCompanyScopeChange(nextScope);
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Home</h1>
          <div className="page-subtitle">Visão operacional por status, empresa e tarefas ({scopeLabel(activeHomeScope)}).</div>
        </div>
        <div className="home-header-actions">
          <button
            className="notify-bell"
            title="Notificações"
            onClick={() => setShowNotifications((v) => !v)}
          >
            <span className="bell">&#128276;</span>
            {unreadNotifications.length > 0 ? <span className="badge">{unreadNotifications.length}</span> : null}
          </button>
        </div>
      </div>

      <div className="row home-controls home-controls-right">
        <input
          placeholder="Competência (MM/AAAA)"
          value={companyComp}
          onChange={(e) => onCompanyCompChange(e.target.value)}
          style={{ minWidth: 190 }}
        />
        <button
          className="primary ghost"
          onClick={() => {
            const comp = parseCompLabel(companyComp);
            if (!comp) {
              alert("Competência inválida. Use MM/AAAA.");
              return;
            }
            const parsed = parseCompetencia(comp);
            onCompanyScopeChange(parsed ? { year: parsed.year, month: parsed.month } : null);
            onGoCompanies();
          }}
        >
          Ver empresas
        </button>
      </div>

      <div className="home-grid">
        <div className="card report">
          <div className="report-left">
            <div className="donut-wrap">
              <DonutChart segments={segments} total={total} />
            </div>
          </div>

          <div className="report-side">
            <div className="legend legend-centered">
              {STATUSES.map((s) => (
                <div key={s} className="legend-row">
                  <span className="dot" style={{ background: STATUS_COLORS[s] }} />
                  <span>{STATUS_LABELS[s]}</span>
                  <span className="muted">{counts[s] || 0}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="card home-feed">
          <div className="feed-header">
            <div>
              <div className="side-title">Feed de vencimentos</div>
              <div className="muted small">Próximas obrigações com data</div>
            </div>
          </div>

          {vencimentos.length === 0 ? (
            <div className="empty-state">
              <div className="empty-title">Sem vencimentos no período</div>
              <div className="empty-caption">Ajuste a competência para ver mais itens</div>
            </div>
          ) : (
            <div className="feed-list">
              {vencimentos.slice(0, 8).map((t) => (
                <div
                  key={t.id}
                  className={`feed-item status-${t.status} clickable`}
                  onDoubleClick={() => onOpenTaskFromNotification && onOpenTaskFromNotification(t)}
                  title="Dê dois cliques para abrir a tarefa"
                >
                  <div className="feed-main">
                    <div className="feed-title">{t.titulo}</div>
                    <div className="feed-meta">
                      {fmtComp(t.competencia)} | {t.tributo || "-"} | {ORGAO_LABELS[t.orgao] || t.orgao}
                    </div>
                  </div>
                  <div className="feed-side">
                    <div className="feed-date">{fmtDate(t.vencimento)}</div>
                    <span className={`status-chip ${t.status}`}>{STATUS_LABELS[t.status]}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {overdue.length > 0 ? (
            <div className="overdue-box">
              <div className="side-title">Atenção: {overdue.length} vencimentos atrasados</div>
              <div className="muted small">Priorize os itens pendentes com data vencida.</div>
            </div>
          ) : null}
        </div>
      </div>

      {showNotifications ? (
        <div className="modal-backdrop" onClick={() => setShowNotifications(false)}>
          <div className="modal notifications-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Notificações</h3>
            <div className="muted small" style={{ marginBottom: 10 }}>
              {unreadNotifications.length} não lida(s)
            </div>
            <div className="notif-filters">
              <button className={notifFilter === "UNREAD" ? "active" : ""} onClick={() => setNotifFilter("UNREAD")}>
                Não lidas
              </button>
              <button className={notifFilter === "READ" ? "active" : ""} onClick={() => setNotifFilter("READ")}>
                Lidas
              </button>
              <button className={notifFilter === "RESOLVED" ? "active" : ""} onClick={() => setNotifFilter("RESOLVED")}>
                Resolvidas
              </button>
            </div>
            <div className="notifications-list">
              {visibleNotifications.length === 0 ? (
                <div className="muted small">Sem notificações.</div>
              ) : (
                visibleNotifications.map((n) => (
                  <div
                    key={n.id}
                    className={`notification-item ${n.is_read ? "read" : "unread"} ${notificationTaskId(n) ? "clickable" : ""}`}
                    onDoubleClick={() => notificationTaskId(n) && openFromNotification(n)}
                    title={notificationTaskId(n) ? "Dê dois cliques para abrir a tarefa" : ""}
                  >
                    <div className="notification-main">
                      <span
                        className={`status-chip ${
                          String(n.type).toLowerCase() === "resolved"
                            ? "CONCLUIDA"
                            : String(n.type).toLowerCase() === "comment" || String(n.type).toLowerCase() === "comment_ack"
                            ? "EM_ANDAMENTO"
                            : "PENDENTE"
                        }`}
                      >
                        {String(n.type).toLowerCase() === "comment"
                          ? "Comentário"
                          : String(n.type).toLowerCase() === "comment_ack"
                          ? "Conferido"
                          : String(n.type).toLowerCase() === "resolved"
                          ? "Resolvida"
                          : "Inconsistência"}
                      </span>
                      <div className="notification-message">{n.message}</div>
                      <div className="muted small">{fmtDateTime(n.created_at)}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="row">
              <button className="ghost" onClick={() => setShowNotifications(false)}>
                Fechar
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ObservationsEditor({ items, onChange, onAutoSave, canEdit }) {
  const [expanded, setExpanded] = useState(new Set());
  const refs = React.useRef([]);
  const list = normalizeObservacoes(items);

  const updateItem = (idx, value) => {
    const next = list.slice();
    next[idx] = value.slice(0, 400);
    onChange(next);
  };

  const addItem = () => {
    const next = [""].concat(list);
    onChange(next);
    setTimeout(() => refs.current[0]?.focus(), 0);
  };

  const removeItem = (idx) => {
    if (!window.confirm("Remover observação?")) return;
    const next = list.slice();
    next.splice(idx, 1);
    onChange(next);
    if (onAutoSave) onAutoSave(next);
  };

  const toggleExpanded = (idx) => {
    const next = new Set(expanded);
    if (next.has(idx)) next.delete(idx);
    else next.add(idx);
    setExpanded(next);
  };

  return (
    <div className="obs-editor">
      <div className="obs-header">
        <div className="obs-title">Observações</div>
        {canEdit ? (
          <button className="ghost icon-btn" onClick={addItem} title="Adicionar observação">
            +
          </button>
        ) : null}
      </div>
      <div className="obs-list">
        {list.length === 0 ? (
          <div className="muted small">Sem Observações.</div>
        ) : (
          list.map((obs, idx) => {
            const long = (obs || "").length > 80;
            const isExpanded = expanded.has(idx);
            return (
              <div key={idx} className="obs-item">
                <textarea
                  ref={(el) => (refs.current[idx] = el)}
                  placeholder="Observação…"
                  rows={isExpanded ? 4 : 1}
                  value={obs}
                  onChange={(e) => updateItem(idx, e.target.value)}
                  onBlur={() => onAutoSave && onAutoSave(list)}
                  disabled={!canEdit}
                  className={isExpanded ? "expanded" : "collapsed"}
                />
                <div className="obs-actions">
                  {long ? (
                    <button className="ghost tiny" onClick={() => toggleExpanded(idx)}>
                      {isExpanded ? "ver menos" : "ver mais"}
                    </button>
                  ) : null}
                  {canEdit ? (
                    <button className="ghost tiny danger" onClick={() => removeItem(idx)} title="Remover">
                      Remover
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

function CompaniesPage({ userId, onOpenCompany, canEdit, competenciaScope, refreshTick }) {

  const [items, setItems] = useState([]);

  const [allTasks, setAllTasks] = useState([]);
  const [users, setUsers] = useState([]);
  const [compFilter, setCompFilter] = useState("");
  const [localScope, setLocalScope] = useState(null);
  const effectiveScope = localScope || competenciaScope;

  const [query, setQuery] = useState("");

  const [regime, setRegime] = useState("Todas");

  const [showCreate, setShowCreate] = useState(false);

  const [companyForm, setCompanyForm] = useState({

    nome: "",

    cnpj: "",

    ie: "",

    regime: "Simples Nacional",

    observacoes: [],

  });



  useEffect(() => {

    api

      .listCompanies(
        userId,
        query,
        regime === "Todas" ? "" : regime,
        effectiveScope?.month ? `${effectiveScope.year}${String(effectiveScope.month).padStart(2, "0")}` : ""
      )

      .then(setItems)

      .catch(() => setItems([]));

  }, [userId, query, regime, effectiveScope, refreshTick]);

  useEffect(() => {
    if (!userId) return;
    api
      .listTasks({ user_id: userId })
      .then(setAllTasks)
      .catch(() => setAllTasks([]));
    api
      .listUsers()
      .then(setUsers)
      .catch(() => setUsers([]));
  }, [userId]);



  const responsavelMap = useMemo(() => {
    const map = new Map();
    users.forEach((u) => map.set(u.id, u.nome));
    return map;
  }, [users]);

  const visibleItems = useMemo(() => items, [items]);



  return (

    <div className="page">

      <div className="page-header">

        <h1>Empresas</h1>

        <input placeholder="Buscar por cliente ou CNPJ..." value={query} onChange={(e) => setQuery(e.target.value)} />

      </div>

        <div className="company-filters">
          <div className="row">
            <input
              className="comp-select"
              placeholder="Competência (MM/AAAA)"
              value={compFilter}
              onChange={(e) => setCompFilter(e.target.value)}
            />
            <button
              className="ghost"
              onClick={() => {
                if (!compFilter.trim()) {
                  setLocalScope(null);
                  return;
                }
                const comp = parseCompLabel(compFilter);
                if (!comp) {
                  alert("Competência inválida. Use MM/AAAA.");
                  return;
                }
                const parsed = parseCompetencia(comp);
                setLocalScope(parsed ? { year: parsed.year, month: parsed.month } : null);
              }}
            >
              Filtrar
            </button>
            {effectiveScope ? (
              <button className="ghost" onClick={() => setLocalScope(null)}>
                Limpar filtro
              </button>
            ) : null}
          </div>
          {effectiveScope ? (
            <div className="scope-pill">Filtro ativo: {scopeLabel(effectiveScope)}</div>
          ) : null}
        </div>

        <div className="filters">

          {REGIMES.map((r) => (

            <button key={r} className={regime === r ? "active" : ""} onClick={() => setRegime(r)}>

              {r}

            </button>

          ))}

          {canEdit ? (

            <button className="primary ghost" onClick={() => setShowCreate(true)}>

              + Nova empresa

            </button>

          ) : null}

        </div>

        {visibleItems.length === 0 ? (

          <div className="empty-state">

            <div className="empty-title">Nenhuma empresa encontrada</div>

            <div className="empty-caption">Ajuste os filtros ou a busca para ver resultados</div>

          </div>

        ) : (

          <div className="company-table">

            <div className="company-row header">

              <div>Cliente</div>

              <div>CNPJ</div>

              <div>IE</div>

              <div>Regime</div>
              <div>Responsável</div>

            </div>

            {visibleItems.map((c) => (

              <div key={c.id} className="company-row" onClick={() => onOpenCompany(c)}>

                <div className="title">{c.nome}</div>

                <div className="meta">{c.cnpj || "-"}</div>

                <div className="meta">{c.ie || "-"}</div>

                <div className="meta">{c.regime || "-"}</div>
                <div className="meta">{responsavelMap.get(c.responsavel_id) || "-"}</div>

              </div>

            ))}

          </div>

        )}

        {showCreate && canEdit && (

          <div className="modal-backdrop" onClick={() => setShowCreate(false)}>

          <div className="modal" onClick={(e) => e.stopPropagation()}>

            <h3>Nova empresa</h3>

            <div className="form-grid">

              <input

                placeholder="Nome"

                value={companyForm.nome}

                onChange={(e) => setCompanyForm({ ...companyForm, nome: e.target.value })}

              />

              <input

                placeholder="CNPJ"

                value={formatCnpj(companyForm.cnpj)}

                onChange={(e) =>

                  setCompanyForm({ ...companyForm, cnpj: onlyDigits(e.target.value).slice(0, 14) })

                }

              />

              <input

                placeholder="IE"

                value={companyForm.ie}

                onChange={(e) => setCompanyForm({ ...companyForm, ie: e.target.value })}

              />

              <select

                value={companyForm.regime}

                onChange={(e) => setCompanyForm({ ...companyForm, regime: e.target.value })}

              >

                <option value="Simples Nacional">Simples Nacional</option>

                <option value="Lucro Presumido">Lucro Presumido</option>

                <option value="Lucro Real">Lucro Real</option>

              </select>


            </div>

            <ObservationsEditor
              items={companyForm.observacoes}
              onChange={(next) => setCompanyForm({ ...companyForm, observacoes: next })}
              onAutoSave={null}
              canEdit={true}
            />

            <div className="row">

              <button

                className="primary"

                onClick={async () => {

                  const payload = { user_id: userId, ...companyForm };

                  await api.createCompany(payload);

                  setCompanyForm({ nome: "", cnpj: "", ie: "", regime: "", observacoes: [] });

                  setShowCreate(false);

                  const rows = await api.listCompanies(userId, query, regime === "Todas" ? "" : regime);

                  setItems(rows);

                }}

              >

                OK

              </button>

              <button className="ghost" onClick={() => setShowCreate(false)}>X</button>

            </div>

          </div>

        </div>

      )}

    </div>

  );

}



function Dashboard({ userId, company, onBack, userRole, competenciaScope, initialTaskId, initialTaskTipo, onTaskLinked }) {

  const [allTasks, setAllTasks] = useState([]);

  const [statusFilter, setStatusFilter] = useState(new Set(STATUSES));
  const [onlyInconsistent, setOnlyInconsistent] = useState(false);

  const [tipo, setTipo] = useState("OBR");

  const [competencia, setCompetencia] = useState("");

  const [selected, setSelected] = useState(null);
  const [comments, setComments] = useState([]);
  const [commentText, setCommentText] = useState("");
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [commentSaving, setCommentSaving] = useState(false);
  const [ackedComments, setAckedComments] = useState(new Set());
  const [ackingCommentId, setAckingCommentId] = useState(null);

  const [uploading, setUploading] = useState(false);

  const [showCreate, setShowCreate] = useState(false);

  const [showEditCompany, setShowEditCompany] = useState(false);

  const [showEditTask, setShowEditTask] = useState(false);

  const canEdit = userRole !== "manager";
  const canChangeResponsavel = userRole === "admin" || userRole === "manager";
  const [users, setUsers] = useState([]);

  const normalizeCompanyForm = (c) => ({
    nome: c?.nome || "",
    cnpj: c?.cnpj || "",
    ie: c?.ie || "",
    regime: c?.regime || "",
    responsavel_id: c?.responsavel_id ?? null,
    observacoes: normalizeObservacoes(c?.observacoes),
  });

  const [companyForm, setCompanyForm] = useState(normalizeCompanyForm(company));
  const [companySnapshot, setCompanySnapshot] = useState(normalizeCompanyForm(company));

  const [taskForm, setTaskForm] = useState({

    titulo: "",

    tipo: tipo,

    orgao: "FED",

    tributo: "",

    competencia: "",

    vencimento: "",

    status: "PENDENTE",

  });

  const [editTaskForm, setEditTaskForm] = useState({

    titulo: "",

    tipo: "OBR",

    orgao: "FED",

    tributo: "",

    competencia: "",

    vencimento: "",

    status: "PENDENTE",

  });



  useEffect(() => {

    api

      .listTasks({ user_id: userId, company_id: company.id, tipo })

      .then(setAllTasks)

      .catch(() => setAllTasks([]));

  }, [userId, company, tipo]);

  useEffect(() => {
    if (!userId) return;
    api
      .listUsers()
      .then(setUsers)
      .catch(() => setUsers([]));
  }, [userId]);



  useEffect(() => {

    const next = normalizeCompanyForm(company);
    setCompanyForm(next);
    setCompanySnapshot(next);

  }, [company]);



  useEffect(() => {

    const onKey = (e) => {

      if (e.key === "Escape") onBack();

    };

    window.addEventListener("keydown", onKey);

    return () => window.removeEventListener("keydown", onKey);

  }, [onBack]);

  useEffect(() => {
    let active = true;
    if (!selected?.id) {
      setComments([]);
      return;
    }
    setCommentsLoading(true);
    api
      .listTaskComments(selected.id, userId)
      .then((rows) => {
        if (!active) return;
        setComments(sortCommentsNewest(rows));
      })
      .catch(() => active && setComments([]))
      .finally(() => active && setCommentsLoading(false));
    return () => {
      active = false;
    };
  }, [selected, userId]);

  useEffect(() => {
    setAckedComments(new Set());
  }, [selected?.id]);

  useEffect(() => {
    if (!initialTaskTipo) return;
    if (initialTaskTipo !== tipo) setTipo(initialTaskTipo);
  }, [initialTaskTipo, tipo]);

  useEffect(() => {
    if (!initialTaskId) return;
    const target = allTasks.find((t) => Number(t.id) === Number(initialTaskId));
    if (!target) return;
    if (target.tipo && target.tipo !== tipo) {
      setTipo(target.tipo);
      return;
    }
    setSelected(target);
    if (onTaskLinked) onTaskLinked();
  }, [allTasks, initialTaskId, onTaskLinked, tipo]);

  const onAddComment = async () => {
    const text = commentText.trim();
    if (!text || !selected?.id) return;
    try {
      setCommentSaving(true);
      await api.addTaskComment(selected.id, userId, text);
      setCommentText("");
      const rows = await api.listTaskComments(selected.id, userId);
      setComments(sortCommentsNewest(rows));
    } catch (e) {
      const msg = e?.message ? String(e.message) : "Falha ao salvar comentário.";
      alert(msg);
    } finally {
      setCommentSaving(false);
    }
  };



  const openPdf = (task) => window.open(api.getPdfUrl(task.id, userId), "_blank");



  const toggleStatus = (s) => {

    setStatusFilter((prev) => {

      const next = new Set(prev);

      if (next.has(s)) next.delete(s);

      else next.add(s);

      if (next.size === 0) STATUSES.forEach((x) => next.add(x));

      return next;

    });

  };



  const competencias = useMemo(() => {

    const set = new Set();

    allTasks.forEach((t) => {

      if (t.competencia && (!competenciaScope || inScope(t.competencia, competenciaScope))) set.add(t.competencia);

    });

    return Array.from(set).sort((a, b) => b.localeCompare(a));

  }, [allTasks, competenciaScope]);



  const getInconsistencies = (t) => {
    const issues = [];
    if (!t.competencia) issues.push("Sem competência");
    if (!t.vencimento) issues.push("Sem vencimento");
    if (t.status && !STATUSES.includes(t.status)) issues.push("Status inválido");
    if (t.status === "ENVIADA" && !t.has_pdf) issues.push("Enviado sem PDF");
    return issues;
  };

  const baseFilteredTasks = useMemo(() => {
    return allTasks.filter((t) => {
      if (!statusFilter.has(t.status)) return false;
      if (competencia && t.competencia !== competencia) return false;
      if (!competencia && competenciaScope && !inScope(t.competencia, competenciaScope)) return false;
      return true;
    });
  }, [allTasks, statusFilter, competencia, competenciaScope]);

  const inconsistentCount = useMemo(
    () => baseFilteredTasks.filter((t) => getInconsistencies(t).length > 0).length,
    [baseFilteredTasks]
  );

  const filteredTasks = useMemo(() => {
    if (!onlyInconsistent) return baseFilteredTasks;
    return baseFilteredTasks.filter((t) => getInconsistencies(t).length > 0);
  }, [baseFilteredTasks, onlyInconsistent]);



  const onAttach = async (task, file) => {

    if (!file) return;

    setUploading(true);

    try {

      await api.uploadPdf(task.id, userId, file);

      const rows = await api.listTasks({ user_id: userId, company_id: company.id, tipo });

      setAllTasks(rows);

      const updated = rows.find((r) => r.id === task.id);

      if (updated) setSelected(updated);

    } finally {

      setUploading(false);

    }

  };



  const updateStatus = async (newStatus) => {

    if (!selected) return;

    await api.updateTaskStatus(selected.id, userId, newStatus);

    const rows = await api.listTasks({ user_id: userId, company_id: company.id, tipo });

    setAllTasks(rows);

    const updated = rows.find((r) => r.id === selected.id);

    if (updated) setSelected(updated);

  };



  const createTask = async () => {

    const comp = parseCompLabel(taskForm.competencia);

    if (taskForm.competencia && !comp) {

      alert("Competência inválida. Use MM/AAAA.");

      return;

    }

    await api.createTask({

      user_id: userId,

      company_id: company.id,

      titulo: taskForm.titulo,

      tipo: taskForm.tipo || tipo,

      orgao: taskForm.orgao,

      tributo: taskForm.tributo,

      competencia: comp,

      vencimento: taskForm.vencimento || null,

      status: taskForm.status,

    });

    const rows = await api.listTasks({ user_id: userId, company_id: company.id, tipo });

    setAllTasks(rows);

    setShowCreate(false);

    setTaskForm({

      titulo: "",

      tipo: tipo,

      orgao: "FED",

      tributo: "",

      competencia: "",

      vencimento: "",

      status: "PENDENTE",

    });

  };



  return (

    <div className="page dashboard-page">

      <div className="page-header company-header">

        <div>

          <div className="company-title-row">
            <h1>{company.nome}</h1>
            <button className="back-btn" onClick={onBack} title="Voltar">
              Voltar
            </button>
          </div>

          <ul className="company-meta edit-list">

            <li>

              <span>CNPJ</span>

              <input

                value={formatCnpj(companyForm.cnpj)}

                onChange={(e) => setCompanyForm({ ...companyForm, cnpj: onlyDigits(e.target.value).slice(0, 14) })}

                disabled={!canEdit}

              />

            </li>

            <li>

              <span>IE</span>

              <input

                value={companyForm.ie}

                onChange={(e) => setCompanyForm({ ...companyForm, ie: e.target.value })}

                disabled={!canEdit}

              />

            </li>

            <li>

              <span>Regime</span>

              <select

                value={companyForm.regime}

                onChange={(e) => setCompanyForm({ ...companyForm, regime: e.target.value })}

                disabled={!canEdit}

              >

                <option value="Simples Nacional">Simples Nacional</option>

                <option value="Lucro Presumido">Lucro Presumido</option>

                <option value="Lucro Real">Lucro Real</option>

              </select>

            </li>
            <li>
              <span>Responsável</span>
              <select
                value={companyForm.responsavel_id ?? ""}
                onChange={async (e) => {
                  const nextId = e.target.value ? Number(e.target.value) : null;
                  setCompanyForm({ ...companyForm, responsavel_id: nextId });
                  if (!canChangeResponsavel || !nextId) return;
                  await api.updateCompanyResponsavel(company.id, userId, nextId);
                  setCompanySnapshot((prev) => ({ ...prev, responsavel_id: nextId }));
                }}
                disabled={!canChangeResponsavel}
              >
                <option value="">-</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.nome}
                  </option>
                ))}
              </select>
            </li>

            <li className="obs-row">

              <span className="label-hidden" aria-hidden="true"></span>

              <ObservationsEditor
                items={companyForm.observacoes}
                onChange={(next) => setCompanyForm({ ...companyForm, observacoes: next })}
                onAutoSave={async (next) => {
                  if (!canEdit) return;
                  await api.updateCompany(company.id, userId, { ...companyForm, observacoes: next });
                  setCompanySnapshot((prev) => ({ ...prev, observacoes: next }));
                }}
                canEdit={canEdit}
              />

            </li>

          </ul>

        </div>

        {canEdit && (companyForm.cnpj !== (company.cnpj || "") ||

          companyForm.ie !== (company.ie || "") ||

          companyForm.regime !== companySnapshot.regime ||
          companyForm.responsavel_id !== companySnapshot.responsavel_id ||
          !obsEqual(companyForm.observacoes, companySnapshot.observacoes)) && (

          <div className="row">

            <button className="primary icon-btn" onClick={async () => {

              await api.updateCompany(company.id, userId, companyForm);
              setCompanySnapshot(companyForm);
              if (canChangeResponsavel && companyForm.responsavel_id) {
                await api.updateCompanyResponsavel(company.id, userId, companyForm.responsavel_id);
              }

            }}>

              {""}

            </button>

            <button className="ghost icon-btn danger" onClick={() => setCompanyForm({

              nome: company.nome || "",

              cnpj: company.cnpj || "",

              ie: company.ie || "",

              regime: company.regime || "",

              observacoes: normalizeObservacoes(company.observacoes),

            })}>

              {""}

            </button>

          </div>

        )}

      </div>

      <div className="tabs">

        <button className={tipo === "OBR" ? "active" : ""} onClick={() => setTipo("OBR")}>

          Obrigações

        </button>

        <button className={tipo === "ACS" ? "active" : ""} onClick={() => setTipo("ACS")}>

          Acessórias

        </button>

      </div>

      <div className="filters">

        <select value={competencia} onChange={(e) => setCompetencia(e.target.value)} className="comp-select">

          <option value="">{scopeLabel(competenciaScope)}</option>

          {competencias.map((c) => (

            <option key={c} value={c}>

              {fmtComp(c)}

            </option>

          ))}

        </select>

        {STATUSES.map((s) => (

          <button key={s} className={statusFilter.has(s) ? "active" : ""} onClick={() => toggleStatus(s)}>

            {STATUS_LABELS[s]}

          </button>

        ))}

        <button
          className={onlyInconsistent ? "active danger" : ""}
          onClick={() => setOnlyInconsistent((v) => !v)}
        >
          Inconsistências{inconsistentCount ? ` (${inconsistentCount})` : ""}
        </button>

        {canEdit ? (

          <button className="primary ghost" onClick={() => setShowCreate(true)}>

            + Nova tarefa

          </button>

        ) : null}

      </div>

      <div className="split">

        <div className="grid">

          {filteredTasks.length === 0 ? (

            <div className="empty-state">

              <div className="empty-title">Nenhuma tarefa encontrada</div>

              <div className="empty-caption">Ajuste os filtros ou crie uma nova tarefa</div>

            </div>

          ) : (

            filteredTasks.map((t) => {
              const issues = getInconsistencies(t);
              return (

              <div

                key={t.id}

                className={`card status-${t.status || ""} ${selected && selected.id === t.id ? "selected" : ""}`}

                onClick={() => setSelected(t)}

              >

                <div className="card-title">
                  {t.titulo}
                  {issues.length > 0 ? <span className="issue-chip">! {issues.length}</span> : null}
                </div>

                <div className="card-meta">{fmtComp(t.competencia)}</div>

                <div className="card-meta muted">Vence em: {fmtDate(t.vencimento)}</div>

                <div className="card-footer">

                  {t.has_pdf ? (
                    <span className="attach">
                      <svg className="attach-icon" viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M21 12.5 11.3 22.2a7 7 0 0 1-9.9-9.9L11.1 2.6a4.5 4.5 0 1 1 6.4 6.4l-9 9a2 2 0 0 1-2.8-2.8l8.2-8.2" />
                      </svg>
                      <span>Anexo</span>
                    </span>
                  ) : (
                    <span />
                  )}

                  <span className={`status-chip ${t.status || ""}`}>{STATUS_LABELS[t.status] || t.status}</span>

                </div>

              </div>

            )})

          )}

        </div>

        <div className="detail card">

          {selected ? (

            <>

              <h3>{selected.titulo}</h3>

              <div className="muted">

                competência: {fmtComp(selected.competencia)}

                <br />

                Vence em: {fmtDate(selected.vencimento)}

                <br />

                Tributo: {selected.tributo || "-"}

                <br />

                Órgão: {ORGAO_LABELS[selected.orgao] || selected.orgao}

                <br />

                Status: {selected.status}

              </div>
              {getInconsistencies(selected).length > 0 ? (
                <div className="inconsistency-box">
                  <div className="side-title">Inconsistências</div>
                  <ul>
                    {getInconsistencies(selected).map((it, idx) => (
                      <li key={idx}>{it}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="row">

                {selected.has_pdf ? (

                  <button onClick={() => openPdf(selected)} className="primary">

                    {selected.pdf_path || "Abrir PDF"}

                  </button>

                ) : (

                  canEdit ? (

                    <label className="attach-bar">

                      <span className="muted">Sem anexo</span>

                      <span className="plus">{uploading ? "..." : "+"}</span>

                      <input

                        type="file"

                        accept="application/pdf"

                        disabled={uploading}

                        onChange={(e) => onAttach(selected, e.target.files?.[0])}

                      />

                    </label>

                  ) : (

                    <span className="muted">Sem anexo</span>

                  )

                )}

                {canEdit ? (

                  <button className="ghost icon-btn" onClick={() => {

                    setEditTaskForm({

                      titulo: selected.titulo,

                      tipo: selected.tipo,

                      orgao: selected.orgao,

                      tributo: selected.tributo || "",

                      competencia: fmtComp(selected.competencia),

                      vencimento: selected.vencimento || "",

                      status: selected.status,

                    });

                    setShowEditTask(true);

                  }}>

                    ...

                  </button>

                ) : null}

              </div>

              {canEdit ? (

                <div className="status-row">

                  {STATUSES.map((s) => (

                    <button

                      key={s}

                      className={selected.status === s ? "active" : ""}

                      onClick={() => updateStatus(s)}

                    >

                      {STATUS_LABELS[s]}

                    </button>

                  ))}

                </div>

              ) : null}

              <div className="comment-section">
                <div className="side-title">Comentários do coordenador</div>
                {commentsLoading ? (
                  <div className="muted small">Carregando comentários...</div>
                ) : (
                  <div className="comment-list">
                    {(!comments || comments.length === 0) && (
                      <div className="muted small">Sem comentários</div>
                    )}
                    {(comments || []).map((c, idx) => {
                      const item = typeof c === "string" ? { text: c } : c || {};
                      const author = users.find((u) => Number(u.id) === Number(item.author_id));
                      const canAck =
                        (userRole === "admin" || userRole === "collab") &&
                        author?.role === "manager" &&
                        item.id &&
                        !ackedComments.has(item.id);
                      return (
                        <div key={item.id || `${item.text || "c"}-${idx}`} className="comment-item">
                          <div className="comment-text">{item.text || "-"}</div>
                          {item.created_at ? (
                            <div className="comment-meta muted small">{fmtDateTime(item.created_at)}</div>
                          ) : null}
                          {canAck ? (
                            <div className="comment-meta">
                              <button
                                className="ghost tiny"
                                disabled={ackingCommentId === item.id}
                                onClick={async () => {
                                  try {
                                    setAckingCommentId(item.id);
                                    await api.ackTaskComment(selected.id, item.id, userId);
                                    setAckedComments((prev) => new Set([...prev, item.id]));
                                  } catch (e) {
                                    alert(e?.message ? String(e.message) : "Falha ao confirmar comentário.");
                                  } finally {
                                    setAckingCommentId(null);
                                  }
                                }}
                              >
                                {ackingCommentId === item.id ? "Enviando..." : "Confere"}
                              </button>
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                )}
                {(userRole === "admin" || userRole === "manager") ? (
                  <div className="comment-form">
                    <textarea
                      placeholder="Comentário..."
                      value={commentText}
                      onChange={(e) => setCommentText(e.target.value)}
                      rows={2}
                    />
                    <button className="primary" onClick={onAddComment} disabled={commentSaving}>
                      {commentSaving ? "Enviando..." : "Enviar"}
                    </button>
                  </div>
                ) : null}
              </div>

            </>

          ) : (

            <div className="muted">

              <div className="row between">

                <span>Selecione uma tarefa</span>

              </div>

            </div>

          )}

        </div>

      </div>

      {showCreate && (

        <div className="modal-backdrop" onClick={() => setShowCreate(false)}>

          <div className="modal" onClick={(e) => e.stopPropagation()}>

            <h3>Nova tarefa</h3>

            <div className="form-grid">

              <input

                placeholder="Título"

                value={taskForm.titulo}

                onChange={(e) => setTaskForm({ ...taskForm, titulo: e.target.value })}

              />

              <select value={taskForm.tipo} onChange={(e) => setTaskForm({ ...taskForm, tipo: e.target.value })}>

                <option value="OBR">OBR</option>

                <option value="ACS">ACS</option>

              </select>

              <select value={taskForm.orgao} onChange={(e) => setTaskForm({ ...taskForm, orgao: e.target.value })}>

                <option value="MUN">Municipal</option>

                <option value="EST">Estadual</option>

                <option value="FED">Federal</option>

              </select>

              <input

                placeholder="Tributo"

                value={taskForm.tributo}

                onChange={(e) => setTaskForm({ ...taskForm, tributo: e.target.value })}

              />

              <input

                placeholder="competência (MM/AAAA)"

                value={taskForm.competencia}

                onChange={(e) =>
                  setTaskForm({ ...taskForm, competencia: formatCompetenciaInput(e.target.value) })
                }
                inputMode="numeric"
                maxLength={7}

              />

              <input

                type="date"

                value={taskForm.vencimento}

                onChange={(e) => setTaskForm({ ...taskForm, vencimento: e.target.value })}

              />

              <select value={taskForm.status} onChange={(e) => setTaskForm({ ...taskForm, status: e.target.value })}>

                {STATUSES.map((s) => (

                  <option key={s} value={s}>

                    {STATUS_LABELS[s]}

                  </option>

                ))}

              </select>

            </div>

            <div className="row">

              <button className="primary" onClick={createTask}>

                OK

              </button>

              <button className="ghost" onClick={() => setShowCreate(false)}>X</button>

            </div>

          </div>

        </div>

      )}

      {showEditCompany && (

        <div className="modal-backdrop" onClick={() => setShowEditCompany(false)}>

          <div className="modal" onClick={(e) => e.stopPropagation()}>

            <h3>Editar empresa</h3>

            <div className="form-grid">

              <input

                placeholder="Nome"

                value={companyForm.nome}

                onChange={(e) => setCompanyForm({ ...companyForm, nome: e.target.value })}

              />

              <input

                placeholder="CNPJ"

                value={formatCnpj(companyForm.cnpj)}

                onChange={(e) =>

                  setCompanyForm({ ...companyForm, cnpj: onlyDigits(e.target.value).slice(0, 14) })

                }

              />

              <input

                placeholder="IE"

                value={companyForm.ie}

                onChange={(e) => setCompanyForm({ ...companyForm, ie: e.target.value })}

              />

              <select

                value={companyForm.regime}

                onChange={(e) => setCompanyForm({ ...companyForm, regime: e.target.value })}

              >

                <option value="Simples Nacional">Simples Nacional</option>

                <option value="Lucro Presumido">Lucro Presumido</option>

                <option value="Lucro Real">Lucro Real</option>

              </select>


            </div>

            <div className="row">

              <button

                className="primary"

                onClick={async () => {

                  await api.updateCompany(company.id, userId, companyForm);
                  setCompanySnapshot(companyForm);

                  setShowEditCompany(false);

                }}

              >

                OK

              </button>

              <button className="ghost" onClick={() => setShowEditCompany(false)}>X</button>

            </div>

          </div>

        </div>

      )}

      {showEditTask && (

        <div className="modal-backdrop" onClick={() => setShowEditTask(false)}>

          <div className="modal" onClick={(e) => e.stopPropagation()}>

            <h3>Editar tarefa</h3>

            <div className="form-grid">

              <input

                placeholder="Título"

                value={editTaskForm.titulo}

                onChange={(e) => setEditTaskForm({ ...editTaskForm, titulo: e.target.value })}

              />

              <select value={editTaskForm.tipo} onChange={(e) => setEditTaskForm({ ...editTaskForm, tipo: e.target.value })}>

                <option value="OBR">OBR</option>

                <option value="ACS">ACS</option>

              </select>

              <select value={editTaskForm.orgao} onChange={(e) => setEditTaskForm({ ...editTaskForm, orgao: e.target.value })}>

                <option value="MUN">Municipal</option>

                <option value="EST">Estadual</option>

                <option value="FED">Federal</option>

              </select>

              <input

                placeholder="Tributo"

                value={editTaskForm.tributo}

                onChange={(e) => setEditTaskForm({ ...editTaskForm, tributo: e.target.value })}

              />

              <input

                placeholder="competência (MM/AAAA)"

                value={editTaskForm.competencia}

                onChange={(e) =>
                  setEditTaskForm({ ...editTaskForm, competencia: formatCompetenciaInput(e.target.value) })
                }
                inputMode="numeric"
                maxLength={7}

              />

              <input

                type="date"

                value={editTaskForm.vencimento}

                onChange={(e) => setEditTaskForm({ ...editTaskForm, vencimento: e.target.value })}

              />

              <select value={editTaskForm.status} onChange={(e) => setEditTaskForm({ ...editTaskForm, status: e.target.value })}>

                {STATUSES.map((s) => (

                  <option key={s} value={s}>

                    {STATUS_LABELS[s]}

                  </option>

                ))}

              </select>

            </div>

            <div className="row">

              <button

                className="primary"

                onClick={async () => {

                  const comp = parseCompLabel(editTaskForm.competencia);

                  if (editTaskForm.competencia && !comp) {

                    alert("Competência inválida. Use MM/AAAA.");

                    return;

                  }

                  await api.updateTask(selected.id, userId, {

                    titulo: editTaskForm.titulo,

                    tipo: editTaskForm.tipo,

                    orgao: editTaskForm.orgao,

                    tributo: editTaskForm.tributo,

                    competencia: comp,

                    vencimento: editTaskForm.vencimento || null,

                    status: editTaskForm.status,

                  });

                  const rows = await api.listTasks({ user_id: userId, company_id: company.id, tipo });

                  setAllTasks(rows);

                  const updated = rows.find((r) => r.id === selected.id);

                  if (updated) setSelected(updated);

                  setShowEditTask(false);

                }}

              >

                OK

              </button>

              <button className="ghost" onClick={() => setShowEditTask(false)}>X</button>

            </div>

          </div>

        </div>

      )}

    </div>

  );

}



function ReportsPage({ userId, refreshTick }) {
  const [tasks, setTasks] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [year, setYear] = useState(new Date().getFullYear());
  const [period, setPeriod] = useState("ANUAL");
  const [selectedStatus, setSelectedStatus] = useState(null);
  const [selectedCompanyId, setSelectedCompanyId] = useState(null);

  useEffect(() => {
    if (!userId) return;
    api
      .listTasks({ user_id: userId })
      .then(setTasks)
      .catch(() => setTasks([]));
    api
      .listCompanies(userId)
      .then(setCompanies)
      .catch(() => setCompanies([]));
  }, [userId, refreshTick]);

  const years = useMemo(() => {
    const set = new Set();
    tasks.forEach((t) => {
      const parsed = parseCompetencia(t.competencia);
      if (parsed) set.add(parsed.year);
    });
    if (set.size === 0) set.add(new Date().getFullYear());
    return Array.from(set).sort((a, b) => b - a);
  }, [tasks]);

  useEffect(() => {
    if (!years.includes(year) && years.length) {
      setYear(years[0]);
    }
  }, [years, year]);

  useEffect(() => {
    setSelectedStatus(null);
    setSelectedCompanyId(null);
  }, [year, period]);

  const scopeValue = useMemo(() => ({ year, period }), [year, period]);
  const filtered = useMemo(() => tasks.filter((t) => inScope(t.competencia, scopeValue)), [tasks, scopeValue]);

  const counts = useMemo(() => {
    const out = {};
    STATUSES.forEach((s) => (out[s] = 0));
    filtered.forEach((t) => {
      out[t.status] = (out[t.status] || 0) + 1;
    });
    return out;
  }, [filtered]);

  const total = STATUSES.reduce((acc, s) => acc + (counts[s] || 0), 0);
  const segments = STATUSES.map((s) => ({
    key: s,
    value: counts[s] || 0,
    color: STATUS_COLORS[s],
  })).filter((s) => s.value > 0);

  const companyMap = useMemo(() => {
    const m = new Map();
    companies.forEach((c) => m.set(c.id, c.nome));
    return m;
  }, [companies]);

  const filteredByStatus = selectedStatus ? filtered.filter((t) => t.status === selectedStatus) : [];

  const companyCounts = useMemo(() => {
    const m = new Map();
    filteredByStatus.forEach((t) => {
      m.set(t.company_id, (m.get(t.company_id) || 0) + 1);
    });
    return Array.from(m.entries()).map(([companyId, count]) => ({
      companyId,
      name: companyMap.get(companyId) || `Empresa ${companyId}`,
      count,
    }));
  }, [filteredByStatus, companyMap]);

  const tasksForCompany = selectedCompanyId
    ? filteredByStatus.filter((t) => t.company_id === selectedCompanyId)
    : [];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Relatórios</h1>
          <div className="page-subtitle">Visão trimestral/anual consolidada de tarefas.</div>
        </div>
      </div>
      <div className="home-grid">
        <div className="card report home-summary">
          <div className="report-left">
            <div className="donut-wrap">
              <DonutChart
                segments={segments}
                total={total}
                onSelect={(s) => {
                  setSelectedStatus(s);
                  setSelectedCompanyId(null);
                }}
              />
            </div>
          </div>
          <div className="report-side">
            <div className="legend-header">
              <div className="row donut-controls" style={{ marginBottom: 8 }}>
                <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
                  {years.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
                <select value={period} onChange={(e) => setPeriod(e.target.value)}>
                  <option value="ANUAL">Anual</option>
                  <option value="T1">T1</option>
                  <option value="T2">T2</option>
                  <option value="T3">T3</option>
                  <option value="T4">T4</option>
                </select>
              </div>
              <div className="side-title">Tarefas ({scopeLabel(scopeValue)})</div>
            </div>
            <div className="legend">
              {STATUSES.map((s) => (
                <div key={s} className="legend-row">
                  <span className="dot" style={{ background: STATUS_COLORS[s] }} />
                  <span>{STATUS_LABELS[s]}</span>
                  <span className="muted">{counts[s] || 0}</span>
                </div>
              ))}
              <div className="muted small" style={{ marginTop: 8 }}>
                Total: {total}
              </div>
            </div>

            {!selectedStatus ? null : !selectedCompanyId ? (
              <>
                <div className="side-title">Empresas com status {STATUS_LABELS[selectedStatus]}</div>
                <div className="side-list">
                  {companyCounts.map((c) => (
                    <button key={c.companyId} onClick={() => setSelectedCompanyId(c.companyId)}>
                      {c.name} | {c.count}
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <>
                <div className="side-title">Tarefas da empresa</div>
                <button className="back" onClick={() => setSelectedCompanyId(null)}>
                  Voltar
                </button>
                <div className="side-list">
                  {tasksForCompany.map((t) => (
                    <div key={t.id} className="side-item">
                      {t.titulo} ({fmtComp(t.competencia)})
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}



function SettingsPage({ theme, onThemeChange, user }) {
  const isAdmin = user?.role === "admin";
  const [serverCfg, setServerCfg] = useState({
    server_host: "127.0.0.1",
    server_port: 8000,
    server_name: "41 Fiscal Hub API",
    environment: "local",
  });
  const [emailCfg, setEmailCfg] = useState({
    smtp_host: "",
    smtp_port: 587,
    smtp_user: "",
    smtp_pass: "",
    smtp_sender: "",
    smtp_tls: true,
  });
  const [userForm, setUserForm] = useState({ nome: "", senha: "1234", role: "collab" });
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!isAdmin || !user?.id) return;
    api.getServerSettings(user.id).then(setServerCfg).catch(() => {});
    api.getEmailSettings(user.id).then(setEmailCfg).catch(() => {});
  }, [isAdmin, user?.id]);

  const saveServer = async () => {
    setMsg("");
    await api.updateServerSettings(user.id, { ...serverCfg, server_port: Number(serverCfg.server_port) || 8000 });
    setMsg("Configuração de servidor salva.");
  };

  const saveEmail = async () => {
    setMsg("");
    await api.updateEmailSettings(user.id, { ...emailCfg, smtp_port: Number(emailCfg.smtp_port) || 587 });
    setMsg("Configuração de e-mail salva.");
  };

  const createLogin = async () => {
    setMsg("");
    if (!userForm.nome.trim()) {
      setMsg("Informe o nome do colaborador.");
      return;
    }
    await api.createUser({
      nome: userForm.nome.trim(),
      senha: userForm.senha || "1234",
      role: userForm.role || "collab",
      is_default: false,
    });
    setUserForm({ nome: "", senha: "1234", role: "collab" });
    setMsg("Login criado com sucesso.");
  };

  return (
    <div className="page">
      <h1>Configurações</h1>

      <div className="card">
        <h3>Tema</h3>
        <div className="row">
          <select value={theme} onChange={(e) => onThemeChange(e.target.value)}>
            <option value="blue">Azul</option>
            <option value="dark">Dark</option>
            <option value="light">Rosa</option>
          </select>
        </div>
      </div>

      {isAdmin ? (
        <>
          <div className="card">
            <h3>Configuração de servidor</h3>
            <div className="form-grid">
              <input
                placeholder="Host"
                value={serverCfg.server_host}
                onChange={(e) => setServerCfg({ ...serverCfg, server_host: e.target.value })}
              />
              <input
                type="number"
                placeholder="Porta"
                value={serverCfg.server_port}
                onChange={(e) => setServerCfg({ ...serverCfg, server_port: e.target.value })}
              />
              <input
                placeholder="Nome do servidor"
                value={serverCfg.server_name}
                onChange={(e) => setServerCfg({ ...serverCfg, server_name: e.target.value })}
              />
              <input
                placeholder="Ambiente"
                value={serverCfg.environment}
                onChange={(e) => setServerCfg({ ...serverCfg, environment: e.target.value })}
              />
            </div>
            <div className="row">
              <button className="primary" onClick={saveServer}>
                Salvar servidor
              </button>
            </div>
          </div>

          <div className="card">
            <h3>Configuração de envio de e-mails</h3>
            <div className="form-grid">
              <input
                placeholder="SMTP host"
                value={emailCfg.smtp_host}
                onChange={(e) => setEmailCfg({ ...emailCfg, smtp_host: e.target.value })}
              />
              <input
                type="number"
                placeholder="SMTP porta"
                value={emailCfg.smtp_port}
                onChange={(e) => setEmailCfg({ ...emailCfg, smtp_port: e.target.value })}
              />
              <input
                placeholder="Usuário SMTP"
                value={emailCfg.smtp_user}
                onChange={(e) => setEmailCfg({ ...emailCfg, smtp_user: e.target.value })}
              />
              <input
                type="password"
                placeholder="Senha SMTP"
                value={emailCfg.smtp_pass}
                onChange={(e) => setEmailCfg({ ...emailCfg, smtp_pass: e.target.value })}
              />
              <input
                placeholder="Remetente"
                value={emailCfg.smtp_sender}
                onChange={(e) => setEmailCfg({ ...emailCfg, smtp_sender: e.target.value })}
              />
              <select
                value={emailCfg.smtp_tls ? "1" : "0"}
                onChange={(e) => setEmailCfg({ ...emailCfg, smtp_tls: e.target.value === "1" })}
              >
                <option value="1">TLS habilitado</option>
                <option value="0">TLS desabilitado</option>
              </select>
            </div>
            <div className="row">
              <button className="primary" onClick={saveEmail}>
                Salvar e-mail
              </button>
            </div>
          </div>

          <div className="card">
            <h3>Novo login de colaborador</h3>
            <div className="form-grid">
              <input
                placeholder="Nome de login"
                value={userForm.nome}
                onChange={(e) => setUserForm({ ...userForm, nome: e.target.value })}
              />
              <input
                placeholder="Senha"
                value={userForm.senha}
                onChange={(e) => setUserForm({ ...userForm, senha: e.target.value })}
              />
              <select
                value={userForm.role}
                onChange={(e) => setUserForm({ ...userForm, role: e.target.value })}
              >
                <option value="collab">Colaborador</option>
                <option value="manager">Coordenador</option>
                <option value="admin">Administrador</option>
              </select>
            </div>
            <div className="row">
              <button className="primary" onClick={createLogin}>
                Criar login
              </button>
            </div>
          </div>
        </>
      ) : null}

      {msg ? <div className="muted small">{msg}</div> : null}
    </div>
  );
}



export default function App() {

  const [user, setUser] = useState(() => readStoredUser());

  const [active, setActive] = useState(() => readStoredActive());

  const [company, setCompany] = useState(null);
  const [restoreCompanyId] = useState(() => readStoredCompanyId());

  const [collapsed, setCollapsed] = useState(false);

  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "blue");

  const [donutScope, setDonutScope] = useState(() => {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1 };
  });

  const [companyScope, setCompanyScope] = useState(null);
  const [linkedTask, setLinkedTask] = useState(null);
  const [menuRefreshTick, setMenuRefreshTick] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [hasRestoredCompany, setHasRestoredCompany] = useState(false);



  useEffect(() => {

    document.body.dataset.theme = theme;

    localStorage.setItem("theme", theme);

  }, [theme]);

  useEffect(() => {
    if (hasRestoredCompany) return;
    if (!user?.id || !restoreCompanyId) {
      setHasRestoredCompany(true);
      return;
    }
    let alive = true;
    api
      .listCompanies(user.id)
      .then((rows) => {
        if (!alive) return;
        const found = (rows || []).find((c) => Number(c.id) === Number(restoreCompanyId));
        if (found) setCompany(found);
      })
      .catch(() => {})
      .finally(() => {
        if (!alive) return;
        setHasRestoredCompany(true);
      });
    return () => {
      alive = false;
    };
  }, [user?.id, restoreCompanyId, hasRestoredCompany]);

  useEffect(() => {
    const baseTitle = "41 Fiscal Hub";
    document.title = unreadCount > 0 ? `(${unreadCount}) ${baseTitle}` : baseTitle;
  }, [unreadCount]);

  useEffect(() => {
    if (!user?.id) {
      setUnreadCount(0);
      return;
    }
    let alive = true;
    const loadUnread = () => {
      api
        .listNotifications(user.id, true)
        .then((rows) => {
          if (!alive) return;
          setUnreadCount(Array.isArray(rows) ? rows.length : 0);
        })
        .catch(() => {});
    };
    loadUnread();
    const timer = setInterval(loadUnread, NOTIFICATION_POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [user?.id]);


  const openTaskFromNotification = async (task) => {
    if (!user?.id || !task?.id || !task?.company_id) return;
    try {
      const companies = await api.listCompanies(user.id);
      const targetCompany = companies.find((c) => Number(c.id) === Number(task.company_id));
      if (!targetCompany) return;
      setLinkedTask({ id: Number(task.id), tipo: task.tipo || "OBR" });
      setCompany(targetCompany);
      const parsed = parseCompetencia(task.competencia);
      if (parsed) {
        setCompanyScope({ year: parsed.year, month: parsed.month });
        setDonutScope({ year: parsed.year, month: parsed.month });
      }
      setActive("home");
    } catch (_) {}
  };


  const handleLogin = (logged, remember) => {
    setUser(logged);
    localStorage.setItem(AUTH_REMEMBER_KEY, remember ? "1" : "0");
    const payload = JSON.stringify(logged);
    if (remember) {
      localStorage.setItem(AUTH_STORAGE_KEY, payload);
      sessionStorage.removeItem(AUTH_STORAGE_KEY);
    } else {
      sessionStorage.setItem(AUTH_STORAGE_KEY, payload);
      localStorage.removeItem(AUTH_STORAGE_KEY);
    }
  };

  useEffect(() => {
    const value = String(active || "home");
    localStorage.setItem(UI_ACTIVE_KEY, value);
    sessionStorage.setItem(UI_ACTIVE_KEY, value);
  }, [active]);

  useEffect(() => {
    const id = company?.id ? String(company.id) : "";
    if (id) {
      localStorage.setItem(UI_COMPANY_KEY, id);
      sessionStorage.setItem(UI_COMPANY_KEY, id);
    } else {
      localStorage.removeItem(UI_COMPANY_KEY);
      sessionStorage.removeItem(UI_COMPANY_KEY);
    }
  }, [company?.id]);

  const content = useMemo(() => {

    if (!user) return <Login onSelect={handleLogin} />;

    if (company)

      return (

        <Dashboard

          userId={user.id}

          company={company}

          userRole={user.role}

          competenciaScope={companyScope}
          initialTaskId={linkedTask?.id}
          initialTaskTipo={linkedTask?.tipo}
          onTaskLinked={() => setLinkedTask(null)}

          onBack={() => setCompany(null)}

        />

      );

    if (active === "home")

      return (

        <HomePage

          userId={user.id}

          donutScope={donutScope}

          onDonutScopeChange={setDonutScope}

          companyScope={companyScope}

          onCompanyScopeChange={setCompanyScope}

          onGoCompanies={() => setActive("companies")}
          onOpenTaskFromNotification={openTaskFromNotification}
          refreshTick={menuRefreshTick}

        />

      );

    if (active === "companies")

      return (

        <CompaniesPage

          userId={user.id}

          onOpenCompany={setCompany}

          canEdit={user.role !== "manager"}

          competenciaScope={companyScope}
          refreshTick={menuRefreshTick}

        />

      );

    if (active === "reports") return <ReportsPage userId={user.id} refreshTick={menuRefreshTick} />;

    if (active === "settings") return <SettingsPage theme={theme} onThemeChange={setTheme} user={user} />;

    return null;

  }, [user, active, company, theme, donutScope, companyScope, linkedTask, menuRefreshTick]);



  if (!user) return content;



  const handleNavigate = (key) => {
    if (!company && active === key) {
      setMenuRefreshTick((v) => v + 1);
    }

    setActive(key);

    setCompany(null);

  };

  const handleLogout = () => {
    setUser(null);
    setCompany(null);
    setLinkedTask(null);
    setActive("home");
    setUnreadCount(0);
    localStorage.removeItem(AUTH_STORAGE_KEY);
    sessionStorage.removeItem(AUTH_STORAGE_KEY);
    localStorage.removeItem(UI_COMPANY_KEY);
    sessionStorage.removeItem(UI_COMPANY_KEY);
  };



  return (

    <div className="app">

      <Sidebar

        active={active}

        onNavigate={handleNavigate}

        collapsed={collapsed}

        onToggle={() => setCollapsed((v) => !v)}

        userRole={user.role}
        onLogout={handleLogout}

      />

      <main className="main">{content}</main>

    </div>

  );

}



function DonutChart({ segments, total, onSelect }) {

  const size = 320;

  const stroke = 28;

  const radius = (size - stroke) / 2;

  const circumference = 2 * Math.PI * radius;

  let offset = 0;



  if (!segments.length) {

    return (

      <svg width={size} height={size}>

        <circle

          cx={size / 2}

          cy={size / 2}

          r={radius}

          stroke="#334155"

          strokeWidth={stroke}

          fill="none"
          style={{ cursor: "default" }}

        />

        <text x="50%" y="50%" textAnchor="middle" dy="6" fill="#94a3b8">

          Sem tarefas

        </text>

      </svg>

    );

  }



  return (

    <svg width={size} height={size}>

      {segments.map((seg, i) => {

        const frac = seg.value / total;

        const dash = circumference * frac;

        const circle = (

          <circle

            key={i}

            cx={size / 2}

            cy={size / 2}

            r={radius}

            stroke={seg.color}

            strokeWidth={stroke}

            fill="none"

            strokeDasharray={`${dash} ${circumference - dash}`}

            strokeDashoffset={-offset}

            strokeLinecap="butt"
            style={{ cursor: onSelect ? "pointer" : "default" }}

            onClick={() => onSelect && onSelect(seg.key)}

          />

        );

        offset += dash;

        return circle;

      })}

      <text x="50%" y="50%" textAnchor="middle" dy="6" fill="#e2e8f0" fontSize="22" fontWeight="600">

        {total}

      </text>

    </svg>

  );

}




