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

const API_BASE = 'http://localhost:5000';
const COLORS = ['#2563eb', '#059669', '#f59e0b', '#dc2626', '#7c3aed', '#0891b2'];

const employees = [
  { name: 'Demo Employee', role: 'Analyst', manager: 'Operations Manager', shift: 'India Day', score: 86, active: '5h 42m', idle: '24m', status: 'Active' },
  { name: 'Night Shift Employee', role: 'Support', manager: 'Operations Manager', shift: 'US Support', score: 78, active: '4h 58m', idle: '38m', status: 'In shift' },
  { name: 'Priya Nair', role: 'QA', manager: 'Operations Manager', shift: 'India Day', score: 91, active: '6h 15m', idle: '15m', status: 'Active' },
  { name: 'Rahul Mehta', role: 'Developer', manager: 'Operations Manager', shift: 'India Day', score: 73, active: '4h 22m', idle: '52m', status: 'Review' },
];

const managerRows = [
  { manager: 'Operations Manager', project: 'Productivity Operations', team: 18, score: 84, productive: '112h', alerts: 3 },
  { manager: 'Delivery Lead', project: 'Client Analytics', team: 14, score: 79, productive: '91h', alerts: 5 },
  { manager: 'Support Lead', project: 'US Support', team: 11, score: 76, productive: '74h', alerts: 6 },
];

const shiftRows = [
  { name: 'India Day Shift', window: '09:30 - 18:30', timezone: 'Asia/Kolkata', coverage: '78%', people: 31 },
  { name: 'US Support Shift', window: '20:00 - 05:00', timezone: 'Asia/Kolkata', coverage: '64%', people: 12 },
  { name: 'Flexible Overlap', window: '13:00 - 22:00', timezone: 'Asia/Kolkata', coverage: '58%', people: 8 },
];

const rules = [
  { target: 'Visual Studio Code', scope: 'App', category: 'Productive', severity: 'Low' },
  { target: 'Microsoft Excel', scope: 'App', category: 'Productive', severity: 'Low' },
  { target: 'youtube.com', scope: 'Domain', category: 'Unproductive', severity: 'Medium' },
  { target: 'Games', scope: 'App', category: 'Prohibited', severity: 'High' },
];

const alerts = [
  { title: 'Prohibited app matched', employee: 'Rahul Mehta', time: '10:42', severity: 'High' },
  { title: 'Idle reason pending', employee: 'Night Shift Employee', time: '09:18', severity: 'Medium' },
  { title: 'Low productivity screenshot', employee: 'Demo Employee', time: '08:55', severity: 'Medium' },
];

const fallbackTrend = [
  { name: 'Mon', productive: 6.4, unproductive: 1.1 },
  { name: 'Tue', productive: 7.1, unproductive: 0.8 },
  { name: 'Wed', productive: 5.9, unproductive: 1.4 },
  { name: 'Thu', productive: 6.8, unproductive: 0.9 },
  { name: 'Fri', productive: 7.4, unproductive: 0.7 },
];

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
  const [productivityData, setProductivityData] = useState(fallbackTrend);
  const [appUsageData, setAppUsageData] = useState([]);
  const [topDomains, setTopDomains] = useState([]);
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
        const res = await axios.get(`${API_BASE}/api/dashboard/admin`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setMetrics(res.data.metrics);
        setProductivityData(res.data.productivity_data?.length ? res.data.productivity_data : fallbackTrend);
        setAppUsageData(res.data.app_usage_data || []);
        setTopDomains(res.data.top_domains || []);
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

  const appChart = appUsageData.length && appUsageData[0].name !== 'No Data'
    ? appUsageData
    : [
        { name: 'VS Code', value: 15400 },
        { name: 'Excel', value: 11800 },
        { name: 'Chrome', value: 9400 },
        { name: 'Teams', value: 7200 },
      ];

  const domainChart = topDomains.length
    ? topDomains
    : [
        { name: 'jira.company.com', value: 8200 },
        { name: 'docs.google.com', value: 6300 },
        { name: 'github.com', value: 5900 },
        { name: 'youtube.com', value: 1800 },
      ];

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
            </div>

            <div className="panel">
              <PanelHeader icon={AlertTriangle} title="Priority Alerts" action={alerts.length} />
              <div className="stack-list">
                {alerts.map((alert) => (
                  <div className="alert-row" key={`${alert.title}-${alert.employee}`}>
                    <span className={`severity ${alert.severity.toLowerCase()}`}>{alert.severity}</span>
                    <div>
                      <strong>{alert.title}</strong>
                      <small>{alert.employee} at {alert.time}</small>
                    </div>
                    <ChevronRight size={16} />
                  </div>
                ))}
              </div>
            </div>

            <div className="panel">
              <PanelHeader icon={Activity} title="Top Applications" action="Top 10" />
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
            </div>

            <div className="panel wide">
              <PanelHeader icon={Building2} title="Manager Performance" action="Drill down" />
              <DataTable
                columns={['Manager', 'Project', 'Team', 'Score', 'Productive', 'Alerts']}
                rows={managerRows.map((row) => [
                  row.manager,
                  row.project,
                  row.team,
                  <span className={`score ${scoreTone(row.score)}`}>{row.score}</span>,
                  row.productive,
                  row.alerts,
                ])}
              />
            </div>
          </section>
        )}

        {activeTab === 'managers' && (
          <section className="page-grid">
            <div className="panel full">
              <PanelHeader icon={Users} title="Manager to Project to Team" action="Hierarchy" />
              <DataTable
                columns={['Manager', 'Project', 'Team Size', 'Productivity Index', 'Productive Time', 'Open Alerts']}
                rows={managerRows.map((row) => [
                  row.manager,
                  row.project,
                  row.team,
                  <span className={`score ${scoreTone(row.score)}`}>{row.score}</span>,
                  row.productive,
                  row.alerts,
                ])}
              />
            </div>
            <div className="panel wide">
              <PanelHeader icon={BarChart3} title="Team Comparison" action="This week" />
              <div className="chart-lg">
                <ResponsiveContainer>
                  <LineChart data={managerRows.map((row) => ({ name: row.manager.split(' ')[0], score: row.score, alerts: row.alerts }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Line dataKey="score" stroke="#2563eb" strokeWidth={3} />
                    <Line dataKey="alerts" stroke="#dc2626" strokeWidth={3} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="panel">
              <PanelHeader icon={ShieldCheck} title="Manager Controls" action="Rules" />
              <div className="control-list">
                <button>Define productive apps</button>
                <button>Define unproductive apps</button>
                <button>Review prohibited alerts</button>
                <button>Export team report</button>
              </div>
            </div>
          </section>
        )}

        {activeTab === 'employees' && (
          <section className="page-grid">
            <div className="panel full">
              <PanelHeader icon={Activity} title="Employee Activity" action={`${employees.length} employees`} />
              <DataTable
                columns={['Employee', 'Role', 'Manager', 'Shift', 'Score', 'Active', 'Idle', 'Status']}
                rows={employees.map((row) => [
                  row.name,
                  row.role,
                  row.manager,
                  row.shift,
                  <span className={`score ${scoreTone(row.score)}`}>{row.score}</span>,
                  row.active,
                  row.idle,
                  <span className="status-pill">{row.status}</span>,
                ])}
              />
            </div>
            <div className="panel wide">
              <PanelHeader icon={Clock} title="Shift Coverage" action="Timezone aware" />
              <DataTable
                columns={['Shift', 'Window', 'Timezone', 'Coverage', 'People']}
                rows={shiftRows.map((row) => [row.name, row.window, row.timezone, row.coverage, row.people])}
              />
            </div>
            <div className="panel">
              <PanelHeader icon={CalendarDays} title="Daily Timeline" action="Today" />
              <div className="timeline">
                {['Login', 'VS Code', 'Excel report', 'Idle reason', 'Teams sync'].map((item, index) => (
                  <div key={item}>
                    <span>{`${9 + index}:00`}</span>
                    <strong>{item}</strong>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {activeTab === 'analytics' && (
          <section className="page-grid">
            <div className="panel wide">
              <PanelHeader icon={Activity} title="Application Analytics" action="Top usage" />
              <DataTable
                columns={['Application', 'Duration', 'Category']}
                rows={appChart.map((row, index) => [row.name, secondsToHours(row.value), index < 2 ? 'Productive' : 'Neutral'])}
              />
            </div>
            <div className="panel">
              <PanelHeader icon={Building2} title="Top Domains" action="Top 10" />
              <LegendList rows={domainChart} />
            </div>
            <div className="panel full">
              <PanelHeader icon={BarChart3} title="Productivity Index Model" action="Weighted" />
              <div className="formula-grid">
                <div><strong>60%</strong><span>Productive time ratio</span></div>
                <div><strong>20%</strong><span>Idle penalty</span></div>
                <div><strong>10%</strong><span>Unproductive usage</span></div>
                <div><strong>10%</strong><span>Liveness and compliance</span></div>
              </div>
            </div>
          </section>
        )}

        {activeTab === 'reports' && (
          <section className="page-grid">
            <div className="panel full">
              <PanelHeader icon={FileSpreadsheet} title="Excel Reports" action="Timezone compatible" />
              <div className="report-grid">
                {['Manager-wise Report', 'Employee-wise Report', 'Shift Summary', 'Prohibited Usage'].map((name) => (
                  <button className="report-card" key={name}>
                    <FileSpreadsheet size={22} />
                    <strong>{name}</strong>
                    <small>Last 7 days</small>
                    <Download size={18} />
                  </button>
                ))}
              </div>
            </div>
          </section>
        )}

        {activeTab === 'settings' && (
          <section className="page-grid">
            <div className="panel wide">
              <PanelHeader icon={Settings} title="App and URL Rules" action="Project scoped" />
              <DataTable
                columns={['Target', 'Scope', 'Category', 'Severity']}
                rows={rules.map((row) => [row.target, row.scope, row.category, <span className={`severity ${row.severity.toLowerCase()}`}>{row.severity}</span>])}
              />
            </div>
            <div className="panel">
              <PanelHeader icon={Clock} title="Shift Configuration" action="Overlap ready" />
              <div className="stack-list compact">
                {shiftRows.map((row) => (
                  <div className="mini-row" key={row.name}>
                    <strong>{row.name}</strong>
                    <small>{row.window} - {row.timezone}</small>
                  </div>
                ))}
              </div>
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

function DataTable({ columns, rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => <td key={`${rowIndex}-${cellIndex}`}>{cell}</td>)}
            </tr>
          ))}
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
