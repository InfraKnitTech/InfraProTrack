import { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  Building2,
  ChevronLeft,
  CalendarDays,
  ChevronRight,
  Clock,
  Download,
  FileSpreadsheet,
  LayoutDashboard,
  LogOut,
  Moon,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Sun,
  User,
  Users,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5002';
const COLORS = ['#2563eb', '#059669', '#f59e0b', '#dc2626', '#7c3aed', '#0891b2'];

function secondsToHours(seconds) {
  return `${(seconds / 3600).toFixed(1)}h`;
}

function scoreTone(score) {
  if (score >= 85) return 'good';
  if (score >= 75) return 'warn';
  return 'risk';
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('overview');
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'light');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [metrics, setMetrics] = useState({
    total_productive: '0h 00m',
    total_idle: '0h 00m',
    total_unproductive: '0h 00m',
    active_employees: 0,
    total_employees: 0,
  });
  const [productivityData, setProductivityData] = useState([]);
  const [appUsageData, setAppUsageData] = useState([]);
  const [topDomains, setTopDomains] = useState([]);
  const [managerSummary, setManagerSummary] = useState([]);
  const [employeeSummary, setEmployeeSummary] = useState([]);
  const [shiftSummary, setShiftSummary] = useState([]);
  const [projectSummary, setProjectSummary] = useState([]);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [pendingAgents, setPendingAgents] = useState([]);

  const user = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem('user')) || {};
    } catch {
      return {};
    }
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const token = localStorage.getItem('token');
        const headers = { Authorization: `Bearer ${token}` };
        const [dashboardRes, appsRes, domainsRes, managerRes, employeeRes, shiftRes, projectRes] = await Promise.all([
          axios.get(`${API_BASE}/api/dashboard/admin`, { headers }),
          axios.get(`${API_BASE}/api/analytics/top-apps`, { headers }),
          axios.get(`${API_BASE}/api/analytics/top-domains`, { headers }),
          axios.get(`${API_BASE}/api/reports/productivity-summary`, { headers, params: { group_by: 'manager' } }),
          axios.get(`${API_BASE}/api/reports/productivity-summary`, { headers, params: { group_by: 'employee' } }),
          axios.get(`${API_BASE}/api/reports/productivity-summary`, { headers, params: { group_by: 'shift' } }),
          axios.get(`${API_BASE}/api/reports/productivity-summary`, { headers, params: { group_by: 'project' } }),
        ]);
        setMetrics(dashboardRes.data.metrics);
        setProductivityData(dashboardRes.data.productivity_data || []);
        setAppUsageData(appsRes.data.items || []);
        setTopDomains(domainsRes.data.items || []);
        setManagerSummary(managerRes.data.rows || []);
        setEmployeeSummary(employeeRes.data.rows || []);
        setShiftSummary(shiftRes.data.rows || []);
        setProjectSummary(projectRes.data.rows || []);
      } catch (err) {
        console.error('Failed to fetch dashboard data', err);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchPendingAgents = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get(`${API_BASE}/api/agents/pending`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPendingAgents(res.data || []);
    } catch (err) {
      console.error('Failed to fetch pending agents', err);
    }
  };

  useEffect(() => {
    fetchPendingAgents();
    const interval = setInterval(fetchPendingAgents, 30000);
    return () => clearInterval(interval);
  }, []);

  const decideAgent = async (requestId, action) => {
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API_BASE}/api/agents/${requestId}/${action}`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchPendingAgents();
    } catch (err) {
      console.error(`Failed to ${action} agent`, err);
    }
  };

  const productiveScore = Math.round(
    ((metrics.active_employees || 0) / Math.max(metrics.total_employees || 1, 1)) * 100
  );

  const appChart = appUsageData;
  const domainChart = topDomains;

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/');
  };

  const nav = [
    ['overview', LayoutDashboard, 'Overview'],
    ['managers', Users, 'Managers'],
    ['employees', Activity, 'Employees'],
    ['analytics', BarChart3, 'Analytics'],
    ['reports', FileSpreadsheet, 'Reports'],
    ['settings', Settings, 'Settings'],
  ];

  return (
    <div className={`app-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      <header className="app-topbar">
        <div className="brand">
          <img src="/logo.png" alt="InfraProTrack logo" />
          <div className="wordmark" aria-label="InfraProTrack">
            <strong className="brand-infra">Infra</strong><strong className="brand-pro">ProTrack</strong>
          </div>
        </div>

        <div className="search-box global-search">
          <Search size={16} />
          <input placeholder="Search employees, projects, apps..." />
        </div>

        <div className="topbar-actions">
          <button className="icon-button bare" aria-label="Refresh dashboard"><RefreshCw size={17} /></button>
          <button className="icon-button" aria-label="Toggle theme" onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>
            {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
          </button>
          <div className="notification-wrap">
            <button className="icon-button bare" aria-label="Notifications" onClick={() => setNotificationOpen((open) => !open)}>
              <Bell size={18} />
              {pendingAgents.length > 0 && <span className="notification-dot">{pendingAgents.length}</span>}
            </button>
            {notificationOpen && (
              <div className="notification-menu">
                <div className="notification-title">Agent approvals</div>
                {pendingAgents.length === 0 ? (
                  <p>No agents waiting for approval.</p>
                ) : pendingAgents.map((agent) => (
                  <div className="pending-agent" key={agent.request_id}>
                    <div>
                      <strong>{agent.hostname}</strong>
                      <small>{agent.os_type} - {agent.username || 'unknown user'}</small>
                    </div>
                    <div className="pending-actions">
                      <button onClick={() => decideAgent(agent.request_id, 'approve')}>Approve</button>
                      <button className="danger" onClick={() => decideAgent(agent.request_id, 'reject')}>Reject</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="user-menu-wrap">
            <button className="user-square" onClick={() => setUserMenuOpen((open) => !open)} aria-expanded={userMenuOpen}>
              <span>{(user.username || 'A').slice(0, 1).toUpperCase()}</span>
              <div>
                <strong>{user.username || 'Administrator'}</strong>
                <small>{user.role || 'Admin'}</small>
              </div>
              <ChevronRight size={15} className="user-chevron" />
            </button>
            {userMenuOpen && (
              <div className="user-menu">
                <button><User size={16} /> Profile</button>
                <button><Settings size={16} /> Settings</button>
                <button className="danger" onClick={handleLogout}><LogOut size={16} /> Logout</button>
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="app-body">
      <aside className="sidebar">
        <button className="sidebar-toggle" onClick={() => setSidebarCollapsed((collapsed) => !collapsed)} aria-label="Expand or collapse sidebar">
          <ChevronLeft size={16} />
        </button>
        <nav className="nav-list">
          {nav.map(([id, Icon, label]) => (
            <button key={id} className={`nav-item ${activeTab === id ? 'active' : ''}`} onClick={() => setActiveTab(id)}>
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="mini-status">
            <span className="pulse" />
            <div>
              <strong>{metrics.active_employees || 0} live agents</strong>
              <small>Polling every 5 seconds</small>
            </div>
          </div>
          <button className="nav-item danger" onClick={handleLogout}>
            <LogOut size={18} />
            <span>Logout</span>
          </button>
        </div>
      </aside>

      <main className="workspace">
        <header className="page-heading">
          <div>
            <h1>{nav.find(([id]) => id === activeTab)?.[2]} Dashboard</h1>
            <p>Overview of employee productivity and infrastructure status</p>
          </div>
        </header>

        {activeTab === 'overview' && (
          <section className="page-grid">
            <div className="metric-card accent-blue">
              <span>Total productive</span>
              <strong>{metrics.total_productive}</strong>
              <small>Across active agents</small>
            </div>
            <div className="metric-card accent-amber">
              <span>Idle time</span>
              <strong>{metrics.total_idle}</strong>
              <small>Reason capture pending</small>
            </div>
            <div className="metric-card accent-red">
              <span>Unproductive</span>
              <strong>{metrics.total_unproductive}</strong>
              <small>Rule-based classification</small>
            </div>
            <div className="metric-card accent-green">
              <span>Active employees</span>
              <strong>{metrics.active_employees} / {metrics.total_employees}</strong>
              <small>{productiveScore}% coverage</small>
            </div>

            <div className="panel wide">
              <PanelHeader icon={BarChart3} title="Productivity Trend" action="Live" />
              {productivityData.length ? (
                <div className="chart-lg">
                  <ResponsiveContainer>
                    <BarChart data={productivityData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="productive" fill="#2563eb" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="unproductive" fill="#ef4444" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : <EmptyState message="No live productivity trend data yet." />}
            </div>

            <div className="panel">
              <PanelHeader icon={AlertTriangle} title="Priority Alerts" action="Live only" />
              <EmptyState message="No live alert feed connected yet." />
            </div>

            <div className="panel">
              <PanelHeader icon={Activity} title="Top Applications" action="Top 10" />
              {appChart.length ? (
                <>
                  <div className="chart-md">
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie data={appChart} dataKey="value" innerRadius={62} outerRadius={92} paddingAngle={3}>
                          {appChart.map((entry, index) => <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />)}
                        </Pie>
                        <Tooltip formatter={(value) => secondsToHours(value)} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <LegendList rows={appChart.slice(0, 4)} />
                </>
              ) : <EmptyState message="No live application usage data yet." />}
            </div>

            <div className="panel wide">
              <PanelHeader icon={Building2} title="Project Performance" action="Live summary" />
              <DataTable
                columns={['Project', 'Employees', 'Productive', 'Active', 'Idle', 'Productivity %']}
                rows={projectSummary.map((row) => [
                  row.group_name,
                  row.employee_count,
                  secondsToHours(row.productive_seconds),
                  secondsToHours(row.active_seconds),
                  secondsToHours(row.idle_seconds),
                  <span className={`score ${scoreTone(Math.round(row.productivity_percent))}`}>{Math.round(row.productivity_percent)}</span>,
                ])}
                emptyMessage="No live project summary data yet."
              />
            </div>
          </section>
        )}

        {activeTab === 'managers' && (
          <section className="page-grid">
            <div className="panel full">
              <PanelHeader icon={Users} title="Manager to Project to Team" action="Hierarchy" />
              <DataTable
                columns={['Manager', 'Employees', 'Productive', 'Active', 'Idle', 'Productivity %']}
                rows={managerSummary.map((row) => [
                  row.group_name,
                  row.employee_count,
                  secondsToHours(row.productive_seconds),
                  secondsToHours(row.active_seconds),
                  secondsToHours(row.idle_seconds),
                  <span className={`score ${scoreTone(Math.round(row.productivity_percent))}`}>{Math.round(row.productivity_percent)}</span>,
                ])}
                emptyMessage="No live manager summary data yet."
              />
            </div>
            <div className="panel wide">
              <PanelHeader icon={BarChart3} title="Team Comparison" action="This week" />
              {managerSummary.length ? (
                <div className="chart-lg">
                  <ResponsiveContainer>
                    <LineChart data={managerSummary.map((row) => ({ name: row.group_name, score: Math.round(row.productivity_percent), employees: row.employee_count }))}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip />
                      <Line dataKey="score" stroke="#2563eb" strokeWidth={3} />
                      <Line dataKey="employees" stroke="#dc2626" strokeWidth={3} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : <EmptyState message="No live manager comparison data yet." />}
            </div>
            <div className="panel">
              <PanelHeader icon={ShieldCheck} title="Manager Controls" action="Rules" />
              <EmptyState message="No live manager control API connected yet." />
            </div>
          </section>
        )}

        {activeTab === 'employees' && (
          <section className="page-grid">
            <div className="panel full">
              <PanelHeader icon={Activity} title="Employee Activity" action="Live summary" />
              <DataTable
                columns={['Employee', 'Logins', 'Logouts', 'Productive', 'Active', 'Idle', 'Productivity %']}
                rows={employeeSummary.map((row) => [
                  row.group_name,
                  row.login_count,
                  row.logout_count,
                  secondsToHours(row.productive_seconds),
                  secondsToHours(row.active_seconds),
                  secondsToHours(row.idle_seconds),
                  <span className={`score ${scoreTone(Math.round(row.productivity_percent))}`}>{Math.round(row.productivity_percent)}</span>,
                ])}
                emptyMessage="No live employee summary data yet."
              />
            </div>
            <div className="panel wide">
              <PanelHeader icon={Clock} title="Shift Coverage" action="Timezone aware" />
              <DataTable
                columns={['Shift', 'Employees', 'Productive', 'Active', 'Idle', 'Productivity %']}
                rows={shiftSummary.map((row) => [
                  row.group_name,
                  row.employee_count,
                  secondsToHours(row.productive_seconds),
                  secondsToHours(row.active_seconds),
                  secondsToHours(row.idle_seconds),
                  <span className={`score ${scoreTone(Math.round(row.productivity_percent))}`}>{Math.round(row.productivity_percent)}</span>,
                ])}
                emptyMessage="No live shift summary data yet."
              />
            </div>
            <div className="panel">
              <PanelHeader icon={CalendarDays} title="Daily Timeline" action="Today" />
              <EmptyState message="No live per-employee timeline API connected yet." />
            </div>
          </section>
        )}

        {activeTab === 'analytics' && (
          <section className="page-grid">
            <div className="panel wide">
              <PanelHeader icon={Activity} title="Application Analytics" action="Top usage" />
              <DataTable
                columns={['Application', 'Duration', 'Category']}
                rows={appChart.map((row) => [row.name, secondsToHours(row.value), row.category || 'Neutral'])}
                emptyMessage="No live application analytics yet."
              />
            </div>
            <div className="panel">
              <PanelHeader icon={Building2} title="Top Domains" action="Top 10" />
              {domainChart.length ? <LegendList rows={domainChart} /> : <EmptyState message="No live domain usage data yet." />}
            </div>
            <div className="panel full">
              <PanelHeader icon={BarChart3} title="Productivity Index Model" action="Pending" />
              <EmptyState message="No live productivity scoring model is connected yet." />
            </div>
          </section>
        )}

        {activeTab === 'reports' && (
          <section className="page-grid">
            <div className="panel full">
              <PanelHeader icon={FileSpreadsheet} title="Excel Reports" action="Timezone compatible" />
              <EmptyState message="No live report export API is connected yet." />
            </div>
          </section>
        )}

        {activeTab === 'settings' && (
          <section className="page-grid">
            <div className="panel wide">
              <PanelHeader icon={Settings} title="App and URL Rules" action="Project scoped" />
              <EmptyState message="No live app rule management API is connected yet." />
            </div>
            <div className="panel">
              <PanelHeader icon={Clock} title="Shift Configuration" action="Overlap ready" />
              <DataTable
                columns={['Shift', 'Employees', 'Productive', 'Idle']}
                rows={shiftSummary.map((row) => [
                  row.group_name,
                  row.employee_count,
                  secondsToHours(row.productive_seconds),
                  secondsToHours(row.idle_seconds),
                ])}
                emptyMessage="No live shift configuration data yet."
              />
            </div>
          </section>
        )}
      </main>
      </div>
    </div>
  );
}

function PanelHeader({ icon: Icon, title, action }) {
  return (
    <div className="panel-header">
      <div>
        <Icon size={18} />
        <h2>{title}</h2>
      </div>
      <span>{action}</span>
    </div>
  );
}

function DataTable({ columns, rows, emptyMessage = 'No live data available.' }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.length ? rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => <td key={`${rowIndex}-${cellIndex}`}>{cell}</td>)}
            </tr>
          )) : (
            <tr>
              <td colSpan={columns.length} className="empty-cell">{emptyMessage}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function LegendList({ rows }) {
  return (
    <div className="legend-list">
      {rows.map((row, index) => (
        <div key={row.name}>
          <span style={{ background: COLORS[index % COLORS.length] }} />
          <strong>{row.name}</strong>
          <small>{secondsToHours(row.value)}</small>
        </div>
      ))}
    </div>
  );
}

function EmptyState({ message }) {
  return <div className="empty-state">{message}</div>;
}
