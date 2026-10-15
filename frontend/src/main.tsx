import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  LayoutDashboard,
  CalendarDays,
  Package,
  GitBranch,
  Bell,
  ShieldCheck,
  LogOut,
  ArrowUpRight,
  Plus,
  Search,
  Building2,
  RefreshCw,
  X,
} from "lucide-react";
import "./style.css";
type Row = Record<string, any>;
const pages = [
  "Overview",
  "Appointments",
  "Inventory",
  "Transfers",
  "Automations",
  "Demo inbox",
  "Audit history",
];
const icons = [
  LayoutDashboard,
  CalendarDays,
  Package,
  GitBranch,
  Activity,
  Bell,
  ShieldCheck,
];
function App() {
  const [session, setSession] = useState<Row | null>(null),
    [page, setPage] = useState("Overview"),
    [data, setData] = useState<Record<string, Row[]>>({}),
    [stats, setStats] = useState<Row>({}),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [query, setQuery] = useState(""),
    [modal, setModal] = useState("");
  const canManage = session?.role !== "nurse";
  async function api(path: string, body?: Row) {
    const r = await fetch("/api/" + path, {
      method: body ? "POST" : "GET",
      headers: {
        "Content-Type": "application/json",
        ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    const j = await r.json();
    if (!r.ok)
      throw Error(
        typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail),
      );
    return j;
  }
  async function load() {
    setBusy(true);
    try {
      const names = [
        "facilities",
        "batches",
        "appointments",
        "transfers",
        "notifications",
        ...(canManage ? ["audit"] : []),
      ];
      const values = await Promise.all(names.map((n) => api(n)));
      setData(Object.fromEntries(names.map((n, i) => [n, values[i]])));
      setStats(await api("overview"));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (session) void load();
  }, [session]);
  async function act(path: string, body: Row = {}) {
    setBusy(true);
    setError("");
    try {
      const r = await api(path, body);
      setNotice(
        r.delivery
          ? `Demo workflow completed: ${r.created} new inbox items, ${r.duplicates_skipped} duplicates skipped.`
          : "Saved successfully.",
      );
      setModal("");
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  const clinic = (id: number) =>
    data.facilities?.find((f) => f.id === id)?.name || `Clinic ${id}`;
  const dt = (value: string) =>
    new Date(value.endsWith("Z") ? value : value + "Z").toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  const filtered = (rows: Row[] = []) =>
    rows.filter(
      (r) =>
        JSON.stringify(r).toLowerCase().includes(query.toLowerCase()) ||
        clinic(r.facility_id).toLowerCase().includes(query.toLowerCase()),
    );
  function badge(value: string) {
    return (
      <span
        className={
          "badge " +
          (value === "cancelled" || value === "Low stock" ? "amber" : "")
        }
      >
        {value.replaceAll("_", " ")}
      </span>
    );
  }
  function bookingTable(rows: Row[]) {
    return (
      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th>Patient reference</th>
              <th>Clinic</th>
              <th>Vaccine</th>
              <th>Appointment</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id}>
                <td>
                  <b>{a.patient_ref}</b>
                  <small>Fictional patient</small>
                </td>
                <td>{clinic(a.facility_id)}</td>
                <td>{a.vaccine}</td>
                <td>{dt(a.slot)}</td>
                <td>{badge(a.status)}</td>
                <td>
                  {a.status === "booked" && (
                    <>
                      <button
                        className="text"
                        onClick={() => setModal("reschedule:" + a.id)}
                      >
                        Reschedule
                      </button>
                      <button
                        className="text"
                        disabled={busy}
                        onClick={() => void act(`appointments/${a.id}/cancel`)}
                      >
                        Cancel
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <p className="empty">No appointments match your search.</p>
        )}
      </div>
    );
  }
  if (!session)
    return (
      <main className="login">
        <section>
          <div className="brand">
            <Activity /> HealthOps<span>CLINIC OPERATIONS</span>
          </div>
          <h1>
            Better care starts
            <br />
            with better operations.
          </h1>
          <p>
            A connected workspace for clinic teams, vaccine inventory, and
            thoughtful automation.
          </p>
          <div className="login-features">
            <span>
              <ShieldCheck /> Role-based access
            </span>
            <span>
              <Activity /> Workflow automation
            </span>
            <span>
              <Package /> Batch-level inventory
            </span>
          </div>
          <small>PORTFOLIO DEMONSTRATION · FICTIONAL DATA ONLY</small>
        </section>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setError("");
            setBusy(true);
            const f = new FormData(e.currentTarget);
            try {
              setSession(await api("auth/login", Object.fromEntries(f)));
            } catch (e) {
              setError(String(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="eyebrow">WELCOME TO HEALTHOPS</div>
          <h2>Sign in to your workspace</h2>
          <p>Use an account created during demo setup.</p>
          <label>
            Username
            <input
              name="username"
              defaultValue="demo.admin"
              autoComplete="username"
              required
            />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button className="primary" disabled={busy}>
            {busy ? "Signing in…" : "Open workspace"} <ArrowUpRight size={16} />
          </button>
          <small>
            Demo roles: admin, manager, nurse.
            <br />
            No real patient information or external messages.
          </small>
        </form>
      </main>
    );
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <Activity /> HealthOps<span>CLINIC OPERATIONS</span>
        </div>
        <div className="workspace">
          <Building2 size={19} />
          <div>
            Demo health network<small>3 fictional clinics</small>
          </div>
        </div>
        <div className="navlabel">WORKSPACE</div>
        <nav>
          {pages
            .filter((p) => canManage || p !== "Audit history")
            .map((p) => {
              const Icon = icons[pages.indexOf(p)];
              return (
                <button
                  key={p}
                  className={page === p ? "selected" : ""}
                  onClick={() => {
                    setPage(p);
                    setQuery("");
                  }}
                >
                  <Icon size={18} />
                  {p}
                  {p === "Demo inbox" && <em>{stats.notifications || 0}</em>}
                </button>
              );
            })}
        </nav>
        <div className="asidebottom">
          <div className="safe">
            <ShieldCheck size={18} />
            <div>
              Safe demo environment
              <small>Notifications stay in the demo inbox.</small>
            </div>
          </div>
          <button
            onClick={() => {
              setSession(null);
              setData({});
              setError("");
            }}
          >
            <LogOut size={17} />
            Sign out
          </button>
        </div>
      </aside>
      <div className="content">
        <header>
          <span>
            Workspace <span className="muted">/ {page}</span>
          </span>
          <div>
            <span className="demo-dot" /> Demo mode{" "}
            <span className="avatar">{session.role[0].toUpperCase()}</span>
            <b>{session.username}</b>
          </div>
        </header>
        <main>
          <div className="heading">
            <div>
              <div className="eyebrow">YOUR CLINIC NETWORK, CONNECTED</div>
              <h1>{page === "Overview" ? "Operations overview" : page}</h1>
              <p>
                {page === "Overview"
                  ? "A clear view of appointments, stock, and the work that needs attention."
                  : "Manage your network with a complete, traceable workflow."}
              </p>
            </div>
            <button
              className="secondary"
              onClick={() => void load()}
              disabled={busy}
            >
              <RefreshCw size={16} />
              {busy ? "Refreshing…" : "Refresh"}
            </button>
          </div>
          {error && (
            <div className="error" role="alert">
              {error}
              <button onClick={() => setError("")}>Dismiss</button>
            </div>
          )}
          {notice && (
            <div className="notice" role="status">
              {notice}
              <button onClick={() => setNotice("")}>Dismiss</button>
            </div>
          )}
          {page === "Overview" && (
            <>
              <div className="metrics">
                {[
                  [
                    "Available doses",
                    stats.available_doses,
                    "Across unexpired batches",
                    Package,
                  ],
                  [
                    "Booked appointments",
                    stats.appointments,
                    "Reserved doses included",
                    CalendarDays,
                  ],
                  [
                    "Clinics connected",
                    stats.facilities,
                    "Fictional demonstration network",
                    Building2,
                  ],
                  [
                    "Low-stock batches",
                    stats.low_stock,
                    "Below 30 available doses",
                    Activity,
                  ],
                ].map(([title, value, sub, Icon]: any) => (
                  <article key={title}>
                    <div>
                      {title}
                      <Icon size={18} />
                    </div>
                    <strong>{value ?? "—"}</strong>
                    <small>{sub}</small>
                  </article>
                ))}
              </div>
              <div className="overviewgrid">
                <section className="panel">
                  <div className="panelhead">
                    <h2>Inventory by clinic</h2>
                    <span className="badge">Live database</span>
                  </div>
                  {data.facilities?.map((f) => {
                    const n =
                      data.batches
                        ?.filter(
                          (b) =>
                            b.facility_id === f.id &&
                            new Date(b.expires) > new Date(),
                        )
                        .reduce((s, b) => s + b.doses, 0) || 0;
                    return (
                      <div className="stockbar" key={f.id}>
                        <div>
                          <b>{f.name}</b>
                          <span>{n} doses</span>
                        </div>
                        <div className="track">
                          <div style={{ width: Math.min(n / 4, 100) + "%" }} />
                        </div>
                        <small>{f.district}</small>
                      </div>
                    );
                  })}
                </section>
                <section className="automation-card">
                  <div className="eyebrow">BUILT FOR FOLLOW-THROUGH</div>
                  <Activity size={30} />
                  <h2>
                    Less manual checking.
                    <br />
                    More time for care.
                  </h2>
                  <p>
                    Preview reminders, expiry warnings and daily reports in a
                    safe demo inbox.
                  </p>
                  <button onClick={() => setPage("Automations")}>
                    Explore automations <ArrowUpRight size={17} />
                  </button>
                  <small>Powered by FastAPI + n8n</small>
                </section>
              </div>
              <section className="panel">
                <div className="panelhead">
                  <h2>Upcoming appointments</h2>
                  <button
                    className="text"
                    onClick={() => setPage("Appointments")}
                  >
                    View all →
                  </button>
                </div>
                {bookingTable(
                  (data.appointments || [])
                    .filter((a) => a.status === "booked")
                    .slice(0, 5),
                )}
              </section>
            </>
          )}
          {["Appointments", "Inventory", "Transfers"].includes(page) && (
            <div className="toolbar">
              <label className="search">
                <Search size={17} />
                <input
                  placeholder="Search records or clinic…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
              {(page === "Appointments" || canManage) && (
                <button className="primary" onClick={() => setModal(page)}>
                  <Plus size={16} />
                  {page === "Appointments"
                    ? "Book appointment"
                    : page === "Inventory"
                      ? "Receive batch"
                      : "Request transfer"}
                </button>
              )}
            </div>
          )}
          {page === "Appointments" && (
            <section className="panel">
              {bookingTable(filtered(data.appointments))}
            </section>
          )}
          {page === "Inventory" && (
            <section className="panel tablewrap">
              <table>
                <thead>
                  <tr>
                    <th>Batch / vaccine</th>
                    <th>Clinic</th>
                    <th>Available</th>
                    <th>Expires</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered(data.batches).map((b) => (
                    <tr key={b.id}>
                      <td>
                        <b>{b.vaccine}</b>
                        <small>{b.code}</small>
                      </td>
                      <td>{clinic(b.facility_id)}</td>
                      <td>
                        <b>{b.doses}</b> doses
                      </td>
                      <td>{dt(b.expires)}</td>
                      <td>
                        {badge(
                          new Date(b.expires) < new Date()
                            ? "Expired"
                            : b.doses < 30
                              ? "Low stock"
                              : "Available",
                        )}
                      </td>
                      <td>
                        {canManage && (
                          <button
                            className="text"
                            onClick={() => setModal("waste:" + b.id)}
                          >
                            Record wastage
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
          {page === "Transfers" && (
            <section className="panel tablewrap">
              <table>
                <thead>
                  <tr>
                    <th>Request</th>
                    <th>Source batch</th>
                    <th>Destination</th>
                    <th>Doses</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered(data.transfers).map((t) => (
                    <tr key={t.id}>
                      <td>
                        TRF-{t.id}
                        <small>{t.requested_by}</small>
                      </td>
                      <td>
                        {data.batches?.find((b) => b.id === t.batch_id)?.code}
                      </td>
                      <td>{clinic(t.destination_id)}</td>
                      <td>{t.doses}</td>
                      <td>{badge(t.status)}</td>
                      <td>
                        {session.role === "admin" && t.status === "pending" && (
                          <button
                            className="text"
                            disabled={busy}
                            onClick={() =>
                              void act(`transfers/${t.id}/approve`)
                            }
                          >
                            Approve transfer
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!data.transfers?.length && (
                <p className="empty">
                  No transfer requests yet. Move available stock between clinics
                  with administrator approval.
                </p>
              )}
            </section>
          )}
          {page === "Automations" && (
            <>
              <div className="notice">
                <ShieldCheck size={18} /> Demo delivery only. These previews use
                the same backend actions as the importable n8n workflows.
              </div>
              <div className="workflowgrid">
                {[
                  [
                    "low-stock",
                    "Low-stock watch",
                    "Review batches below 30 doses and identify replenishment needs.",
                    "Every 6 hours",
                  ],
                  [
                    "reminders",
                    "Appointment reminders",
                    "Prepare reminders for fictional patients with visits in the next 24 hours.",
                    "Hourly",
                  ],
                  [
                    "expiry",
                    "Expiry early warning",
                    "Highlight batches expiring within 30 days for inventory review.",
                    "Daily",
                  ],
                  [
                    "daily-report",
                    "Daily operations digest",
                    "Summarize booked appointments and available unexpired doses.",
                    "Daily",
                  ],
                ].map(([key, title, desc, schedule]) => (
                  <section className="panel workflow" key={key}>
                    <div className="workflowicon">
                      <GitBranch />
                    </div>
                    <span className="badge">{schedule}</span>
                    <h2>{title}</h2>
                    <p>{desc}</p>
                    <div className="flowsteps">
                      Schedule → API check → Demo inbox
                    </div>
                    <button
                      className="secondary"
                      disabled={busy || !canManage}
                      onClick={() => void act("demo/workflows/" + key)}
                    >
                      Run demo preview <ArrowUpRight size={16} />
                    </button>
                  </section>
                ))}
              </div>
              <p className="muted">
                n8n schedules remain inactive until imported, configured, and
                enabled. Repeated runs skip duplicate inbox entries.
              </p>
            </>
          )}
          {page === "Demo inbox" && (
            <div className="inbox">
              {data.notifications?.map((n) => (
                <section className="panel message" key={n.id}>
                  <div className="workflowicon">
                    <Bell />
                  </div>
                  <div>
                    <div className="panelhead">
                      <h2>{n.kind.replaceAll("-", " ")}</h2>
                      {badge(n.status)}
                    </div>
                    <p>{n.message}</p>
                    <small>{dt(n.created)} · No external delivery</small>
                  </div>
                </section>
              ))}
              {!data.notifications?.length && (
                <section className="panel empty">
                  Your demo inbox is empty. Run an automation preview to create
                  a sample report.
                </section>
              )}
            </div>
          )}
          {page === "Audit history" && (
            <section className="panel tablewrap">
              <table>
                <thead>
                  <tr>
                    <th>Action</th>
                    <th>Actor</th>
                    <th>Details</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {data.audit?.map((a) => (
                    <tr key={a.id}>
                      <td>{a.action}</td>
                      <td>{a.actor}</td>
                      <td>{a.detail}</td>
                      <td>{dt(a.created)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!data.audit?.length && (
                <p className="empty">
                  Actions will appear here as your team uses the workspace.
                </p>
              )}
            </section>
          )}
          <footer>
            HealthOps · Full-stack clinic operations{" "}
            <span>Fictional data · Portfolio demonstration</span>
          </footer>
        </main>
      </div>
      {modal && (
        <div className="modalback">
          <form
            className="modal"
            onSubmit={(e) => {
              e.preventDefault();
              const f = Object.fromEntries(
                new FormData(e.currentTarget),
              ) as Row;
              for (const k of [
                "facility_id",
                "destination_id",
                "batch_id",
                "doses",
              ])
                if (f[k]) f[k] = Number(f[k]);
              for (const k of ["slot", "expires"])
                if (f[k]) f[k] = new Date(f[k]).toISOString();
              const path =
                modal === "Appointments"
                  ? "appointments"
                  : modal === "Inventory"
                    ? "batches"
                    : modal === "Transfers"
                      ? "transfers"
                      : modal.startsWith("reschedule")
                        ? `appointments/${modal.split(":")[1]}/reschedule`
                        : `batches/${modal.split(":")[1]}/waste`;
              void act(path, f);
            }}
          >
            <div className="panelhead">
              <h2>
                {modal.includes(":")
                  ? modal.startsWith("waste")
                    ? "Record wastage"
                    : "Reschedule appointment"
                  : modal === "Appointments"
                    ? "Book appointment"
                    : modal === "Inventory"
                      ? "Receive stock batch"
                      : "Request stock transfer"}
              </h2>
              <button
                type="button"
                aria-label="Close"
                onClick={() => setModal("")}
              >
                <X />
              </button>
            </div>
            {["Appointments", "Inventory", "Transfers"].includes(modal) && (
              <label>
                {modal === "Transfers" ? "Destination clinic" : "Clinic"}
                <select
                  name={
                    modal === "Transfers" ? "destination_id" : "facility_id"
                  }
                >
                  {data.facilities?.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {modal === "Appointments" && (
              <label>
                Fictional patient reference
                <input
                  name="patient_ref"
                  placeholder="DEMO-10025"
                  pattern="DEMO-[A-Z0-9-]{3,40}"
                  required
                />
              </label>
            )}
            {["Appointments", "Inventory"].includes(modal) && (
              <label>
                Vaccine
                <select name="vaccine">
                  {["MMR", "Hepatitis B", "Polio"].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
            )}
            {(modal === "Appointments" || modal.startsWith("reschedule")) && (
              <label>
                Appointment date and time (your local time)
                <input name="slot" type="datetime-local" required />
              </label>
            )}
            {modal === "Inventory" && (
              <>
                <label>
                  Batch code
                  <input name="code" required minLength={2} maxLength={60} />
                </label>
                <label>
                  Expiry date
                  <input name="expires" type="datetime-local" required />
                </label>
              </>
            )}
            {modal === "Transfers" && (
              <label>
                Source batch
                <select name="batch_id">
                  {data.batches?.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.code} · {clinic(b.facility_id)} · {b.doses} doses
                    </option>
                  ))}
                </select>
              </label>
            )}
            {(modal === "Inventory" ||
              modal === "Transfers" ||
              modal.startsWith("waste")) && (
              <label>
                Doses
                <input
                  name="doses"
                  type="number"
                  min="1"
                  max="100000"
                  required
                />
              </label>
            )}
            {modal.startsWith("waste") && (
              <label>
                Reason
                <input name="reason" minLength={4} maxLength={200} required />
              </label>
            )}
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <button className="primary" disabled={busy}>
              Save {busy ? "…" : ""}
            </button>
            <small>Only fictional data belongs in this demonstration.</small>
          </form>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
