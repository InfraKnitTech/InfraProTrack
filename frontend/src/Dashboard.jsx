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
  FolderTree,
  LayoutDashboard,
  LogOut,
  Moon,
  Plus,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Sun,
  Trash2,
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

function createGroupMemberDraft(index = 0) {
  return {
    client_key: `member-${Date.now()}-${Math.random().toString(36).slice(2, 8)}-${index}`,
    parent_client_key: '',
    member_type: 'user',
    ref_id: '',
    department_name: '',
    label_override: '',
  };
}

function memberOptions(groupOptions, memberType) {
  if (memberType === 'manager') return groupOptions.managers || [];
  if (memberType === 'project') return groupOptions.projects || [];
  if (memberType === 'department') return groupOptions.departments || [];
  return groupOptions.users || [];
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
  const [groups, setGroups] = useState([]);
  const [groupsLoading, setGroupsLoading] = useState(false);
  const [groupOptions, setGroupOptions] = useState({ users: [], managers: [], projects: [], departments: [] });
  const [groupForm, setGroupForm] = useState({
    name: '',
    category_name: '',
    description: '',
    members: [createGroupMemberDraft()],
  });
  const [rules, setRules] = useState([]);
  const [rulesLoading, setRulesLoading] = useState(false);
  const [ruleForm, setRuleForm] = useState({
    app_name: '',
    domain: '',
    category: 'productive',
    severity: 'medium',
  });
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

  const fetchRules = async () => {
    try {
      setRulesLoading(true);
      const token = localStorage.getItem('token');
      const headers = { Authorization: `Bearer ${token}` };
      const res = await axios.get(`${API_BASE}/api/rules`, { headers });
      setRules(res.data.items || []);
    } catch (err) {
      console.error('Failed to fetch rules', err);
      setRules([]);
    } finally {
      setRulesLoading(false);
    }
  };

  const fetchGroups = async () => {
    try {
      setGroupsLoading(true);
      const token = localStorage.getItem('token');
      const headers = { Authorization: `Bearer ${token}` };
      const [groupsRes, optionsRes] = await Promise.all([
        axios.get(`${API_BASE}/api/groups`, { headers }),
        axios.get(`${API_BASE}/api/groups/options`, { headers }),
      ]);
      setGroups(groupsRes.data.items || []);
      setGroupOptions(optionsRes.data || { users: [], managers: [], projects: [], departments: [] });
    } catch (err) {
      console.error('Failed to fetch groups', err);
      setGroups([]);
    } finally {
      setGroupsLoading(false);
    }
  };

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

  useEffect(() => {
    fetchRules();
  }, []);

  useEffect(() => {
    fetchGroups();
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

  const handleRuleChange = (event) => {
    const { name, value } = event.target;
    setRuleForm((current) => ({ ...current, [name]: value }));
  };

  const createRule = async (event) => {
    event.preventDefault();
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API_BASE}/api/rules`, ruleForm, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setRuleForm({
        app_name: '',
        domain: '',
        category: 'productive',
        severity: 'medium',
      });
      fetchRules();
    } catch (err) {
      console.error('Failed to create rule', err);
    }
  };

  const removeRule = async (ruleId) => {
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`${API_BASE}/api/rules/${ruleId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchRules();
    } catch (err) {
      console.error('Failed to delete rule', err);
    }
  };

  const handleGroupFormChange = (event) => {
    const { name, value } = event.target;
    setGroupForm((current) => ({ ...current, [name]: value }));
  };

  const handleGroupMemberChange = (clientKey, field, value) => {
    setGroupForm((current) => ({
      ...current,
      members: current.members.map((member) => {
        if (member.client_key !== clientKey) {
          return member;
        }
        if (field === 'member_type') {
          return {
            ...member,
            member_type: value,
            ref_id: '',
            department_name: '',
            parent_client_key: member.parent_client_key,
          };
        }
        return { ...member, [field]: value };
      }),
    }));
  };

  const addGroupMember = () => {
    setGroupForm((current) => ({
      ...current,
      members: [...current.members, createGroupMemberDraft(current.members.length)],
    }));
  };

  const removeGroupMember = (clientKey) => {
    setGroupForm((current) => {
      const members = current.members.filter((member) => member.client_key !== clientKey);
      return {
        ...current,
        members: members.map((member) => (
          member.parent_client_key === clientKey
            ? { ...member, parent_client_key: '' }
            : member
        )),
      };
    });
  };

  const createGroup = async (event) => {
    event.preventDefault();
    try {
      const token = localStorage.getItem('token');
      const headers = { Authorization: `Bearer ${token}` };
      const payload = {
        name: groupForm.name,
        category_name: groupForm.category_name,
        description: groupForm.description,
        members: groupForm.members.map((member, index) => ({
          client_key: member.client_key,
          parent_client_key: member.parent_client_key || null,
          member_type: member.member_type,
          user_id: member.member_type === 'user' ? Number(member.ref_id) : null,
          manager_user_id: member.member_type === 'manager' ? Number(member.ref_id) : null,
          project_id: member.member_type === 'project' ? Number(member.ref_id) : null,
          department_name: member.member_type === 'department' ? member.department_name : null,
          label_override: member.label_override || null,
          sort_order: index,
        })),
      };
      await axios.post(`${API_BASE}/api/groups`, payload, { headers });
      setGroupForm({
        name: '',
        category_name: '',
        description: '',
        members: [createGroupMemberDraft()],
      });
      fetchGroups();
    } catch (err) {
      console.error('Failed to create group', err);
    }
  };

  const deleteGroup = async (groupId) => {
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`${API_BASE}/api/groups/${groupId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchGroups();
    } catch (err) {
      console.error('Failed to delete group', err);
    }
  };

  const nav = [
    ['overview', LayoutDashboard, 'Overview'],
    ['groups', FolderTree, 'Groups'],
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

        {activeTab === 'groups' && (
          <section className="page-grid">
            <div className="panel full">
              <PanelHeader icon={FolderTree} title="Custom Group Builder" action="Reusable categories" />
              <div className="group-builder">
                <form className="group-form" onSubmit={createGroup}>
                  <div className="group-form-grid">
                    <label>
                      <span>Group name</span>
                      <input className="input-field" name="name" value={groupForm.name} onChange={handleGroupFormChange} placeholder="North Delivery Cluster" required />
                    </label>
                    <label>
                      <span>Category</span>
                      <input className="input-field" name="category_name" value={groupForm.category_name} onChange={handleGroupFormChange} placeholder="Department, Category, Special Review" required />
                    </label>
                    <label className="group-form-wide">
                      <span>Description</span>
                      <input className="input-field" name="description" value={groupForm.description} onChange={handleGroupFormChange} placeholder="Optional note about why this group exists" />
                    </label>
                  </div>

                  <div className="group-member-stack">
                    {groupForm.members.map((member, index) => (
                      <div className="group-member-row" key={member.client_key}>
                        <div className="group-member-grid">
                          <label>
                            <span>Type</span>
                            <select className="input-field" value={member.member_type} onChange={(event) => handleGroupMemberChange(member.client_key, 'member_type', event.target.value)}>
                              <option value="user">User</option>
                              <option value="manager">Manager team</option>
                              <option value="project">Project team</option>
                              <option value="department">Department</option>
                            </select>
                          </label>
                          <label>
                            <span>Target</span>
                            <select
                              className="input-field"
                              value={member.member_type === 'department' ? member.department_name : member.ref_id}
                              onChange={(event) => handleGroupMemberChange(
                                member.client_key,
                                member.member_type === 'department' ? 'department_name' : 'ref_id',
                                event.target.value,
                              )}
                            >
                              <option value="">Select</option>
                              {memberOptions(groupOptions, member.member_type).map((option) => (
                                <option key={option.id} value={option.department_name || option.ref_id}>{option.label}</option>
                              ))}
                            </select>
                          </label>
                          <label>
                            <span>Parent</span>
                            <select className="input-field" value={member.parent_client_key} onChange={(event) => handleGroupMemberChange(member.client_key, 'parent_client_key', event.target.value)}>
                              <option value="">Root node</option>
                              {groupForm.members
                                .filter((candidate) => candidate.client_key !== member.client_key)
                                .map((candidate, candidateIndex) => (
                                  <option key={candidate.client_key} value={candidate.client_key}>
                                    {candidate.label_override || `${candidate.member_type} ${candidateIndex + 1}`}
                                  </option>
                                ))}
                            </select>
                          </label>
                          <label>
                            <span>Custom label</span>
                            <input className="input-field" value={member.label_override} onChange={(event) => handleGroupMemberChange(member.client_key, 'label_override', event.target.value)} placeholder="Optional display label" />
                          </label>
                        </div>
                        <div className="group-member-actions">
                          <span>Node {index + 1}</span>
                          <button type="button" className="table-action danger" onClick={() => removeGroupMember(member.client_key)} aria-label={`Remove member ${index + 1}`}>
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="group-builder-actions">
                    <button type="button" className="btn btn-secondary" onClick={addGroupMember}>
                      <Plus size={16} />
                      Add member
                    </button>
                    <button type="submit" className="btn btn-primary">
                      <Plus size={16} />
                      Create group
                    </button>
                  </div>
                </form>
              </div>
            </div>

            <div className="panel full">
              <PanelHeader icon={BarChart3} title="Group Rollups" action="Live group-wise data" />
              <DataTable
                columns={['Category', 'Group', 'Employees', 'Productive', 'Active', 'Idle', 'Productivity %', 'Members', 'Action']}
                rows={groups.map((group) => [
                  group.category_name,
                  group.name,
                  group.summary.employee_count,
                  secondsToHours(group.summary.productive_seconds),
                  secondsToHours(group.summary.active_seconds),
                  secondsToHours(group.summary.idle_seconds),
                  <span className={`score ${scoreTone(Math.round(group.summary.productivity_percent))}`}>{Math.round(group.summary.productivity_percent)}</span>,
                  group.members.length,
                  <button className="table-action danger" onClick={() => deleteGroup(group.id)} aria-label={`Delete group ${group.name}`}>
                    <Trash2 size={15} />
                  </button>,
                ])}
                emptyMessage={groupsLoading ? 'Loading live group data...' : 'No custom groups created yet.'}
              />
            </div>

            <div className="panel full">
              <PanelHeader icon={Users} title="Group Hierarchies" action="Users can repeat across groups" />
              {groups.length ? (
                <div className="group-cards">
                  {groups.map((group) => (
                    <div className="group-card" key={group.id}>
                      <div className="group-card-head">
                        <div>
                          <strong>{group.name}</strong>
                          <small>{group.category_name}</small>
                        </div>
                        <div className="group-chip-row">
                          <span className="status-pill">{group.summary.employee_count} employees</span>
                          <span className={`score ${scoreTone(Math.round(group.summary.productivity_percent))}`}>{Math.round(group.summary.productivity_percent)}%</span>
                        </div>
                      </div>
                      {group.description && <p>{group.description}</p>}
                      <GroupHierarchy members={group.members} />
                    </div>
                  ))}
                </div>
              ) : <EmptyState message="No live custom group hierarchy exists yet." />}
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
              <div className="rules-layout">
                <form className="rule-form" onSubmit={createRule}>
                  <div className="rule-form-grid">
                    <label>
                      <span>Application</span>
                      <input
                        className="input-field"
                        name="app_name"
                        value={ruleForm.app_name}
                        onChange={handleRuleChange}
                        placeholder="Visual Studio Code"
                      />
                    </label>
                    <label>
                      <span>Domain</span>
                      <input
                        className="input-field"
                        name="domain"
                        value={ruleForm.domain}
                        onChange={handleRuleChange}
                        placeholder="youtube.com"
                      />
                    </label>
                    <label>
                      <span>Category</span>
                      <select className="input-field" name="category" value={ruleForm.category} onChange={handleRuleChange}>
                        <option value="productive">Productive</option>
                        <option value="unproductive">Unproductive</option>
                        <option value="prohibited">Prohibited</option>
                        <option value="neutral">Neutral</option>
                      </select>
                    </label>
                    <label>
                      <span>Severity</span>
                      <select className="input-field" name="severity" value={ruleForm.severity} onChange={handleRuleChange}>
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                      </select>
                    </label>
                  </div>
                  <button className="btn btn-primary rule-submit" type="submit">
                    <Plus size={16} />
                    Add rule
                  </button>
                </form>

                <DataTable
                  columns={['Application', 'Domain', 'Category', 'Severity', 'Project', 'Action']}
                  rows={rules.map((row) => [
                    row.app_name || '-',
                    row.domain || '-',
                    <span className={`status-pill rule-${row.category}`}>{row.category}</span>,
                    <span className={`severity ${row.severity}`}>{row.severity}</span>,
                    row.project_name || 'All projects',
                    <button className="table-action danger" onClick={() => removeRule(row.id)} aria-label={`Delete rule ${row.id}`}>
                      <Trash2 size={15} />
                    </button>,
                  ])}
                  emptyMessage={rulesLoading ? 'Loading live rules...' : 'No live rules are configured yet.'}
                />
              </div>
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

function GroupHierarchy({ members }) {
  const tree = useMemo(() => {
    const byParent = new Map();
    members.forEach((member) => {
      const parentKey = member.parent_member_id || 0;
      const bucket = byParent.get(parentKey) || [];
      bucket.push(member);
      byParent.set(parentKey, bucket);
    });
    return byParent;
  }, [members]);

  const renderBranch = (parentId = 0, depth = 0) => {
    const branch = tree.get(parentId) || [];
    return branch.map((member) => (
      <div className="group-tree-node" key={member.id} style={{ marginLeft: `${depth * 18}px` }}>
        <div className="group-tree-row">
          <strong>{member.display_label}</strong>
          <small>{member.member_type}</small>
          <span className="status-pill">{member.employee_count} people</span>
        </div>
        {renderBranch(member.id, depth + 1)}
      </div>
    ));
  };

  return <div className="group-tree">{renderBranch()}</div>;
}
