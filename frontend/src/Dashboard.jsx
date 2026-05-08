import { useEffect, useMemo, useRef, useState } from 'react';
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
  Briefcase,
  ChevronLeft,
  CalendarDays,
  ChevronRight,
  Clock,
  Download,
  Eye,
  FileSpreadsheet,
  FolderTree,
  LayoutDashboard,
  LogOut,
  MoreVertical,
  Moon,
  Plus,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Sun,
  Trash2,
  User,
  UserPlus,
  Users,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { clearSession, isTokenValid } from './auth';

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

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

function blankEmployeeForm() {
  return {
    username: '',
    full_name: '',
    email: '',
    password: '',
    employee_code: '',
    department: '',
    phone: '',
    location: '',
    designation: '',
    employment_status: 'working',
    manager_id: '',
    project_id: '',
    shift_id: '',
    assets: [{ asset_type: '', asset_name: '', asset_tag: '', notes: '' }],
    schedule: [],
  };
}

function blankShiftForm() {
  return {
    name: '',
    start_time: '09:00',
    end_time: '18:00',
    timezone: 'Asia/Kolkata',
    grace_minutes: 10,
    is_overnight: 0,
  };
}

function employeeFormFromRecord(employee) {
  return {
    username: employee.username || '',
    full_name: employee.full_name || '',
    email: employee.email || '',
    password: '',
    employee_code: employee.employee_code || '',
    department: employee.department || '',
    phone: employee.phone || '',
    location: employee.location || '',
    designation: employee.designation || '',
    employment_status: employee.employment_status || 'working',
    manager_id: employee.manager_id || '',
    project_id: employee.project_id || '',
    shift_id: employee.shift_id || '',
    assets: employee.assets?.length ? employee.assets.map((asset) => ({
      asset_type: asset.asset_type || '',
      asset_name: asset.asset_name || '',
      asset_tag: asset.asset_tag || '',
      notes: asset.notes || '',
    })) : [{ asset_type: '', asset_name: '', asset_tag: '', notes: '' }],
    schedule: employee.schedule?.map((item) => ({
      weekday: item.weekday,
      shift_id: item.shift_id,
    })) || [],
  };
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('overview');
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'light');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef(null);
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
  const [employees, setEmployees] = useState([]);
  const [employeeFilters, setEmployeeFilters] = useState({
    name: '',
    department: '',
    designation: '',
    project_id: '',
    shift_id: '',
    status: '',
  });
  const [employeeSubTab, setEmployeeSubTab] = useState('directory');
  const [employeeForm, setEmployeeForm] = useState(blankEmployeeForm());
  const [editingEmployeeId, setEditingEmployeeId] = useState(null);
  const [selectedEmployeeInsight, setSelectedEmployeeInsight] = useState(null);
  const [employeeInsight, setEmployeeInsight] = useState(null);
  const [shifts, setShifts] = useState([]);
  const [shiftForm, setShiftForm] = useState(blankShiftForm());
  const [editingShiftId, setEditingShiftId] = useState(null);
  const [shiftSummary, setShiftSummary] = useState([]);
  const [projectSummary, setProjectSummary] = useState([]);
  const [groups, setGroups] = useState([]);
  const [groupsLoading, setGroupsLoading] = useState(false);
  const [groupOptions, setGroupOptions] = useState({ users: [], managers: [], projects: [], departments: [] });
  const [groupForm, setGroupForm] = useState({
    name: '',
    category_name: '',
    description: '',
    leader_user_id: '',
    leader_title: '',
    members: [createGroupMemberDraft()],
  });
  const [editingGroupId, setEditingGroupId] = useState(null);
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

  const departmentOptions = useMemo(() => (
    [...new Set(employees.map((employee) => employee.department).filter(Boolean))].sort()
  ), [employees]);

  const designationOptions = useMemo(() => (
    [...new Set(employees.map((employee) => employee.designation).filter(Boolean))].sort()
  ), [employees]);

  const getAuthHeaders = () => {
    const token = localStorage.getItem('token');
    if (!isTokenValid(token)) {
      clearSession();
      navigate('/');
      return null;
    }
    return { Authorization: `Bearer ${token}` };
  };

  const handleAuthError = (err) => {
    if (err?.response?.status === 401) {
      clearSession();
      navigate('/');
      return true;
    }
    return false;
  };

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    const closeUserMenu = (event) => {
      if (!userMenuRef.current || userMenuRef.current.contains(event.target)) {
        return;
      }
      setUserMenuOpen(false);
    };

    document.addEventListener('mousedown', closeUserMenu);
    return () => document.removeEventListener('mousedown', closeUserMenu);
  }, []);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const headers = getAuthHeaders();
        if (!headers) {
          return;
        }
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
        if (handleAuthError(err)) {
          return;
        }
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
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const res = await axios.get(`${API_BASE}/api/rules`, { headers });
      setRules(res.data.items || []);
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to fetch rules', err);
      setRules([]);
    } finally {
      setRulesLoading(false);
    }
  };

  const fetchGroups = async () => {
    try {
      setGroupsLoading(true);
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const [groupsRes, optionsRes] = await Promise.all([
        axios.get(`${API_BASE}/api/groups`, { headers }),
        axios.get(`${API_BASE}/api/groups/options`, { headers }),
      ]);
      setGroups(groupsRes.data.items || []);
      setGroupOptions(optionsRes.data || { users: [], managers: [], projects: [], departments: [] });
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to fetch groups', err);
      setGroups([]);
    } finally {
      setGroupsLoading(false);
    }
  };

  const fetchEmployeeDirectory = async () => {
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const params = Object.fromEntries(
        Object.entries(employeeFilters).filter(([, value]) => value !== '')
      );
      const [employeesRes, shiftsRes] = await Promise.all([
        axios.get(`${API_BASE}/api/employees`, { headers, params }),
        axios.get(`${API_BASE}/api/shifts`, { headers }),
      ]);
      setEmployees(employeesRes.data.items || []);
      setShifts(shiftsRes.data.items || []);
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to fetch employees and shifts', err);
    }
  };

  const fetchPendingAgents = async () => {
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const res = await axios.get(`${API_BASE}/api/agents/pending`, {
        headers,
      });
      setPendingAgents(res.data || []);
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
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

  useEffect(() => {
    fetchEmployeeDirectory();
  }, [employeeFilters]);

  const decideAgent = async (requestId, action) => {
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      await axios.post(`${API_BASE}/api/agents/${requestId}/${action}`, {}, {
        headers,
      });
      fetchPendingAgents();
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
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
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      await axios.post(`${API_BASE}/api/rules`, ruleForm, {
        headers,
      });
      setRuleForm({
        app_name: '',
        domain: '',
        category: 'productive',
        severity: 'medium',
      });
      fetchRules();
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to create rule', err);
    }
  };

  const removeRule = async (ruleId) => {
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      await axios.delete(`${API_BASE}/api/rules/${ruleId}`, {
        headers,
      });
      fetchRules();
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
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
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const payload = {
        name: groupForm.name,
        category_name: groupForm.category_name,
        description: groupForm.description,
        leader_user_id: groupForm.leader_user_id ? Number(groupForm.leader_user_id) : null,
        leader_title: groupForm.leader_title || null,
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
      if (editingGroupId) {
        await axios.put(`${API_BASE}/api/groups/${editingGroupId}`, payload, { headers });
      } else {
        await axios.post(`${API_BASE}/api/groups`, payload, { headers });
      }
      resetGroupForm();
      fetchGroups();
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to create group', err);
    }
  };

  const deleteGroup = async (groupId) => {
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      await axios.delete(`${API_BASE}/api/groups/${groupId}`, {
        headers,
      });
      fetchGroups();
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to delete group', err);
    }
  };

  const startEditGroup = (group) => {
    const keyById = new Map(group.members.map((member, index) => [member.id, `existing-${group.id}-${member.id}-${index}`]));
    setEditingGroupId(group.id);
    setGroupForm({
      name: group.name,
      category_name: group.category_name,
      description: group.description || '',
      leader_user_id: group.leader_user_id || '',
      leader_title: group.leader_title || '',
      members: group.members.map((member, index) => ({
        client_key: keyById.get(member.id),
        parent_client_key: member.parent_member_id ? (keyById.get(member.parent_member_id) || '') : '',
        member_type: member.member_type,
        ref_id: member.user_id || member.manager_user_id || member.project_id || '',
        department_name: member.department_name || '',
        label_override: member.label_override || '',
      })),
    });
    setActiveTab('groups');
  };

  const resetGroupForm = () => {
    setEditingGroupId(null);
    setGroupForm({
      name: '',
      category_name: '',
      description: '',
      leader_user_id: '',
      leader_title: '',
      members: [createGroupMemberDraft()],
    });
  };

  const handleEmployeeChange = (event) => {
    const { name, value } = event.target;
    setEmployeeForm((current) => ({ ...current, [name]: value }));
  };

  const handleEmployeeAssetChange = (index, field, value) => {
    setEmployeeForm((current) => ({
      ...current,
      assets: current.assets.map((asset, assetIndex) => (
        assetIndex === index ? { ...asset, [field]: value } : asset
      )),
    }));
  };

  const addEmployeeAsset = () => {
    setEmployeeForm((current) => ({
      ...current,
      assets: [...current.assets, { asset_type: '', asset_name: '', asset_tag: '', notes: '' }],
    }));
  };

  const removeEmployeeAsset = (index) => {
    setEmployeeForm((current) => ({
      ...current,
      assets: current.assets.filter((_, assetIndex) => assetIndex !== index),
    }));
  };

  const setEmployeeWeekdayShift = (weekday, shiftId) => {
    setEmployeeForm((current) => {
      const schedule = current.schedule.filter((item) => item.weekday !== weekday);
      if (shiftId) {
        schedule.push({ weekday, shift_id: Number(shiftId) });
      }
      schedule.sort((a, b) => a.weekday - b.weekday);
      return { ...current, schedule };
    });
  };

  const employeeScheduleShiftId = (weekday) => {
    const row = employeeForm.schedule.find((item) => item.weekday === weekday);
    return row?.shift_id || '';
  };

  const saveEmployee = async (event) => {
    event.preventDefault();
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const payload = {
        ...employeeForm,
        manager_id: employeeForm.manager_id ? Number(employeeForm.manager_id) : null,
        project_id: employeeForm.project_id ? Number(employeeForm.project_id) : null,
        shift_id: employeeForm.shift_id ? Number(employeeForm.shift_id) : null,
        password: employeeForm.password || null,
        assets: employeeForm.assets.filter((asset) => asset.asset_name.trim()),
        schedule: employeeForm.schedule,
      };
      if (editingEmployeeId) {
        await axios.put(`${API_BASE}/api/employees/${editingEmployeeId}`, payload, { headers });
      } else {
        await axios.post(`${API_BASE}/api/employees`, payload, { headers });
      }
      resetEmployeeForm();
      fetchEmployeeDirectory();
      fetchGroups();
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to save employee', err);
    }
  };

  const editEmployee = (employee) => {
    setEditingEmployeeId(employee.id);
    setEmployeeForm(employeeFormFromRecord(employee));
    setEmployeeSubTab('form');
  };

  const resetEmployeeForm = () => {
    setEditingEmployeeId(null);
    setEmployeeForm(blankEmployeeForm());
    setEmployeeSubTab('directory');
  };

  const offboardEmployee = async (employeeId) => {
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      await axios.delete(`${API_BASE}/api/employees/${employeeId}`, { headers });
      fetchEmployeeDirectory();
      setEmployeeSubTab('directory');
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to offboard employee', err);
    }
  };

  const loadEmployeeInsight = async (employee, nextTab = 'details') => {
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      setSelectedEmployeeInsight(employee);
      setEmployeeSubTab(nextTab);
      const res = await axios.get(`${API_BASE}/api/employees/${employee.id}/insights`, { headers });
      setEmployeeInsight(res.data);
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to load employee insights', err);
    }
  };

  const handleShiftChange = (event) => {
    const { name, value } = event.target;
    setShiftForm((current) => ({ ...current, [name]: value }));
  };

  const handleEmployeeFilterChange = (event) => {
    const { name, value } = event.target;
    setEmployeeFilters((current) => ({ ...current, [name]: value }));
  };

  const saveShift = async (event) => {
    event.preventDefault();
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const payload = {
        ...shiftForm,
        grace_minutes: Number(shiftForm.grace_minutes || 0),
        is_overnight: Number(shiftForm.is_overnight || 0),
      };
      if (editingShiftId) {
        await axios.put(`${API_BASE}/api/shifts/${editingShiftId}`, payload, { headers });
      } else {
        await axios.post(`${API_BASE}/api/shifts`, payload, { headers });
      }
      setShiftForm(blankShiftForm());
      setEditingShiftId(null);
      fetchEmployeeDirectory();
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to save shift', err);
    }
  };

  const editShift = (shift) => {
    setEditingShiftId(shift.id);
    setShiftForm({
      name: shift.name,
      start_time: shift.start_time?.slice(0, 5) || '09:00',
      end_time: shift.end_time?.slice(0, 5) || '18:00',
      timezone: shift.timezone || 'Asia/Kolkata',
      grace_minutes: shift.grace_minutes ?? 10,
      is_overnight: shift.is_overnight || 0,
    });
    setEmployeeSubTab('shifts');
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
          <div className="user-menu-wrap" ref={userMenuRef}>
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
                    <label>
                      <span>Leader</span>
                      <select className="input-field" name="leader_user_id" value={groupForm.leader_user_id} onChange={handleGroupFormChange}>
                        <option value="">No leader assigned</option>
                        {groupOptions.users.map((option) => (
                          <option key={option.id} value={option.ref_id}>{option.label}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Leader title</span>
                      <input className="input-field" name="leader_title" value={groupForm.leader_title} onChange={handleGroupFormChange} placeholder="CTO, CEO, Senior Engineer, Team Lead" />
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
                    {editingGroupId && (
                      <button type="button" className="btn btn-secondary" onClick={resetGroupForm}>
                        Cancel edit
                      </button>
                    )}
                    <button type="submit" className="btn btn-primary">
                      <Plus size={16} />
                      {editingGroupId ? 'Save group' : 'Create group'}
                    </button>
                  </div>
                </form>
              </div>
            </div>

            <div className="panel full">
              <PanelHeader icon={BarChart3} title="Group Rollups" action="Live group-wise data" />
              <DataTable
                columns={['Category', 'Group', 'Leader', 'Employees', 'Productive', 'Active', 'Idle', 'Productivity %', 'Members', 'Actions']}
                rows={groups.map((group) => [
                  group.category_name,
                  group.name,
                  group.leader_name ? `${group.leader_name}${group.leader_title ? ` (${group.leader_title})` : ''}` : '-',
                  group.summary.employee_count,
                  secondsToHours(group.summary.productive_seconds),
                  secondsToHours(group.summary.active_seconds),
                  secondsToHours(group.summary.idle_seconds),
                  <span className={`score ${scoreTone(Math.round(group.summary.productivity_percent))}`}>{Math.round(group.summary.productivity_percent)}</span>,
                  group.members.length,
                  <div className="table-action-row">
                    <button className="table-action" onClick={() => startEditGroup(group)} aria-label={`Edit group ${group.name}`}>
                      Edit
                    </button>
                    <button className="table-action danger" onClick={() => deleteGroup(group.id)} aria-label={`Delete group ${group.name}`}>
                      <Trash2 size={15} />
                    </button>
                  </div>,
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
                          {group.leader_name && <span className="status-pill">{group.leader_name}{group.leader_title ? ` - ${group.leader_title}` : ''}</span>}
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
              {employeeSubTab === 'directory' && (
                <>
                  <div className="module-header">
                    <div>
                      <Users size={18} />
                      <div>
                        <h2>Workforce Directory</h2>
                        <p>Employees, assignments, status, assets, and monitoring access</p>
                      </div>
                    </div>
                    <div className="module-actions">
                      <button className="btn btn-secondary" onClick={() => setEmployeeSubTab('shifts')}>
                        <Clock size={16} />
                        Shift timings
                      </button>
                      <button className="btn btn-primary" onClick={() => { resetEmployeeForm(); setEmployeeSubTab('form'); }}>
                        <UserPlus size={16} />
                        Add employee
                      </button>
                    </div>
                  </div>
                  <div className="employee-filter-grid">
                    <input className="input-field" name="name" value={employeeFilters.name} onChange={handleEmployeeFilterChange} placeholder="Search name, username, email" />
                    <select className="input-field" name="department" value={employeeFilters.department} onChange={handleEmployeeFilterChange}>
                      <option value="">All departments</option>
                      {departmentOptions.map((department) => <option key={department} value={department}>{department}</option>)}
                    </select>
                    <select className="input-field" name="designation" value={employeeFilters.designation} onChange={handleEmployeeFilterChange}>
                      <option value="">All designations</option>
                      {designationOptions.map((designation) => <option key={designation} value={designation}>{designation}</option>)}
                    </select>
                    <select className="input-field" name="project_id" value={employeeFilters.project_id} onChange={handleEmployeeFilterChange}>
                      <option value="">All projects</option>
                      {groupOptions.projects.map((option) => <option key={option.id} value={option.ref_id}>{option.label}</option>)}
                    </select>
                    <select className="input-field" name="shift_id" value={employeeFilters.shift_id} onChange={handleEmployeeFilterChange}>
                      <option value="">All shifts</option>
                      {shifts.map((shift) => <option key={shift.id} value={shift.id}>{shift.name}</option>)}
                    </select>
                    <select className="input-field" name="status" value={employeeFilters.status} onChange={handleEmployeeFilterChange}>
                      <option value="">All statuses</option>
                      <option value="working">Working</option>
                      <option value="retired">Retired</option>
                      <option value="left">Left org</option>
                      <option value="inactive">Inactive</option>
                    </select>
                  </div>
                  <DataTable
                    columns={['Employee', 'Department', 'Designation', 'Status', 'Email', 'Phone', 'Location', 'Shift', 'Created by', 'Assets', 'Actions']}
                    rows={employees.map((employee) => [
                      employee.full_name,
                      employee.department || '-',
                      employee.designation || '-',
                      <span className={`status-pill employee-${employee.employment_status}`}>{employee.employment_status}</span>,
                      employee.email,
                      employee.phone || '-',
                      employee.location || '-',
                      employee.shift_name || '-',
                      employee.created_by_name || '-',
                      employee.assets?.length || 0,
                      <div className="table-action-row">
                        <button className="table-action" onClick={() => loadEmployeeInsight(employee, 'details')} aria-label={`Open details for ${employee.full_name}`}>
                          <MoreVertical size={15} />
                        </button>
                      </div>,
                    ])}
                    emptyMessage="No employees found for the selected filters."
                  />
                </>
              )}

              {employeeSubTab === 'form' && (
                <>
                  <div className="module-header">
                    <div>
                      <UserPlus size={18} />
                      <div>
                        <h2>{editingEmployeeId ? 'Edit Employee' : 'Add Employee'}</h2>
                        <p>Profile, assignment, assets, and weekday schedule</p>
                      </div>
                    </div>
                    <button className="btn btn-secondary" onClick={resetEmployeeForm}>Back to workforce</button>
                  </div>
                  <form className="employee-form" onSubmit={saveEmployee}>
                    <div className="employee-form-grid">
                      <label><span>Full name</span><input className="input-field" name="full_name" value={employeeForm.full_name} onChange={handleEmployeeChange} required /></label>
                      <label><span>Username</span><input className="input-field" name="username" value={employeeForm.username} onChange={handleEmployeeChange} required /></label>
                      <label><span>Email</span><input className="input-field" type="email" name="email" value={employeeForm.email} onChange={handleEmployeeChange} required /></label>
                      <label><span>Password</span><input className="input-field" type="password" name="password" value={employeeForm.password} onChange={handleEmployeeChange} placeholder={editingEmployeeId ? 'Leave unchanged' : 'Default: Employee@123'} /></label>
                      <label><span>Employee code</span><input className="input-field" name="employee_code" value={employeeForm.employee_code} onChange={handleEmployeeChange} /></label>
                      <label><span>Department / Team</span><input className="input-field" name="department" value={employeeForm.department} onChange={handleEmployeeChange} placeholder="Delivery, Support, Engineering" /></label>
                      <label><span>Designation</span><input className="input-field" name="designation" value={employeeForm.designation} onChange={handleEmployeeChange} placeholder="Senior Engineer" /></label>
                      <label><span>Status</span>
                        <select className="input-field" name="employment_status" value={employeeForm.employment_status} onChange={handleEmployeeChange}>
                          <option value="working">Working</option>
                          <option value="retired">Retired</option>
                          <option value="left">Left org</option>
                          <option value="inactive">Inactive</option>
                        </select>
                      </label>
                      <label><span>Phone</span><input className="input-field" name="phone" value={employeeForm.phone} onChange={handleEmployeeChange} /></label>
                      <label><span>Location</span><input className="input-field" name="location" value={employeeForm.location} onChange={handleEmployeeChange} /></label>
                      <label><span>Manager / Leader</span>
                        <select className="input-field" name="manager_id" value={employeeForm.manager_id} onChange={handleEmployeeChange}>
                          <option value="">No manager / leader</option>
                          {groupOptions.users.map((option) => <option key={option.id} value={option.ref_id}>{option.label}</option>)}
                        </select>
                      </label>
                      <label><span>Project</span>
                        <select className="input-field" name="project_id" value={employeeForm.project_id} onChange={handleEmployeeChange}>
                          <option value="">No project</option>
                          {groupOptions.projects.map((option) => <option key={option.id} value={option.ref_id}>{option.label}</option>)}
                        </select>
                      </label>
                      <label><span>Default shift</span>
                        <select className="input-field" name="shift_id" value={employeeForm.shift_id} onChange={handleEmployeeChange}>
                          <option value="">No default shift</option>
                          {shifts.map((shift) => <option key={shift.id} value={shift.id}>{shift.name}</option>)}
                        </select>
                      </label>
                    </div>

                    <div className="employee-subsection">
                      <div className="subsection-head">
                        <strong>Weekly custom schedule</strong>
                        <small>Leave days blank to use the default shift.</small>
                      </div>
                      <div className="weekday-grid">
                        {WEEKDAYS.map((day, index) => (
                          <label key={day}>
                            <span>{day}</span>
                            <select className="input-field" value={employeeScheduleShiftId(index)} onChange={(event) => setEmployeeWeekdayShift(index, event.target.value)}>
                              <option value="">Default shift</option>
                              {shifts.map((shift) => <option key={shift.id} value={shift.id}>{shift.name}</option>)}
                            </select>
                          </label>
                        ))}
                      </div>
                    </div>

                    <div className="employee-subsection">
                      <div className="subsection-head">
                        <strong>Assigned assets</strong>
                        <button type="button" className="btn btn-secondary" onClick={addEmployeeAsset}><Plus size={15} /> Add asset</button>
                      </div>
                      <div className="asset-stack">
                        {employeeForm.assets.map((asset, index) => (
                          <div className="asset-row" key={index}>
                            <input className="input-field" value={asset.asset_type} onChange={(event) => handleEmployeeAssetChange(index, 'asset_type', event.target.value)} placeholder="Laptop, phone, ID card" />
                            <input className="input-field" value={asset.asset_name} onChange={(event) => handleEmployeeAssetChange(index, 'asset_name', event.target.value)} placeholder="Asset name" />
                            <input className="input-field" value={asset.asset_tag} onChange={(event) => handleEmployeeAssetChange(index, 'asset_tag', event.target.value)} placeholder="Asset tag" />
                            <input className="input-field" value={asset.notes} onChange={(event) => handleEmployeeAssetChange(index, 'notes', event.target.value)} placeholder="Notes" />
                            <button type="button" className="table-action danger" onClick={() => removeEmployeeAsset(index)}><Trash2 size={15} /></button>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="group-builder-actions">
                      <button className="btn btn-primary" type="submit">{editingEmployeeId ? 'Save employee' : 'Create employee'}</button>
                    </div>
                  </form>
                </>
              )}

              {employeeSubTab === 'shifts' && (
                <div className="shift-manager">
                  <div className="module-header">
                    <div>
                      <Clock size={18} />
                      <div>
                        <h2>Shift Timings</h2>
                        <p>Reusable shift blocks for default and weekday schedules</p>
                      </div>
                    </div>
                    <button className="btn btn-secondary" onClick={() => setEmployeeSubTab('directory')}>Back to workforce</button>
                  </div>
                  <form className="shift-form" onSubmit={saveShift}>
                    <div className="shift-form-grid">
                      <label><span>Shift name</span><input className="input-field" name="name" value={shiftForm.name} onChange={handleShiftChange} placeholder="Block A Shift" required /></label>
                      <label><span>Start</span><input className="input-field" type="time" name="start_time" value={shiftForm.start_time} onChange={handleShiftChange} required /></label>
                      <label><span>End</span><input className="input-field" type="time" name="end_time" value={shiftForm.end_time} onChange={handleShiftChange} required /></label>
                      <label><span>Timezone</span><input className="input-field" name="timezone" value={shiftForm.timezone} onChange={handleShiftChange} /></label>
                      <label><span>Grace minutes</span><input className="input-field" type="number" name="grace_minutes" value={shiftForm.grace_minutes} onChange={handleShiftChange} /></label>
                      <label><span>Overnight</span>
                        <select className="input-field" name="is_overnight" value={shiftForm.is_overnight} onChange={handleShiftChange}>
                          <option value={0}>No</option>
                          <option value={1}>Yes</option>
                        </select>
                      </label>
                    </div>
                    <div className="group-builder-actions">
                      {editingShiftId && <button type="button" className="btn btn-secondary" onClick={() => { setEditingShiftId(null); setShiftForm(blankShiftForm()); }}>Cancel edit</button>}
                      <button className="btn btn-primary" type="submit">{editingShiftId ? 'Save shift' : 'Create shift'}</button>
                    </div>
                  </form>
                  <DataTable
                    columns={['Shift', 'Timing', 'Timezone', 'Grace', 'Overnight', 'Action']}
                    rows={shifts.map((shift) => [
                      shift.name,
                      `${shift.start_time?.slice(0, 5)} - ${shift.end_time?.slice(0, 5)}`,
                      shift.timezone,
                      `${shift.grace_minutes} min`,
                      shift.is_overnight ? 'Yes' : 'No',
                      <button className="table-action" onClick={() => editShift(shift)}><MoreVertical size={15} /></button>,
                    ])}
                    emptyMessage="No custom shift blocks created yet."
                  />
                </div>
              )}

              {employeeSubTab === 'details' && (
                employeeInsight ? (
                  <div className="employee-insight">
                    <div className="module-header">
                      <div>
                        <Eye size={18} />
                        <div>
                          <h2>{employeeInsight.employee.full_name}</h2>
                          <p>{employeeInsight.employee.designation || 'Employee'} - {employeeInsight.employee.department || 'Unassigned department'}</p>
                        </div>
                      </div>
                      <div className="module-actions">
                        <button className="btn btn-secondary" onClick={() => setEmployeeSubTab('directory')}>Back</button>
                        <button className="btn btn-secondary" onClick={() => editEmployee(employeeInsight.employee)}>Edit</button>
                        <button className="btn btn-secondary danger" onClick={() => offboardEmployee(employeeInsight.employee.id)}>Mark left</button>
                      </div>
                    </div>
                    <div className="insight-strip">
                      <div><span>Employee</span><strong>{employeeInsight.employee.full_name}</strong></div>
                      <div><span>Productive</span><strong>{secondsToHours(employeeInsight.productive_seconds)}</strong></div>
                      <div><span>Idle</span><strong>{secondsToHours(employeeInsight.idle_seconds)}</strong></div>
                      <div><span>Score</span><strong>{Math.round(employeeInsight.productivity_percent)}%</strong></div>
                    </div>
                    <div className="detail-grid">
                      <div><span>Email</span><strong>{employeeInsight.employee.email}</strong></div>
                      <div><span>Phone</span><strong>{employeeInsight.employee.phone || '-'}</strong></div>
                      <div><span>Location</span><strong>{employeeInsight.employee.location || '-'}</strong></div>
                      <div><span>Status</span><strong>{employeeInsight.employee.employment_status}</strong></div>
                      <div><span>Manager / Leader</span><strong>{employeeInsight.employee.manager_name || '-'}</strong></div>
                      <div><span>Project</span><strong>{employeeInsight.employee.project_name || '-'}</strong></div>
                      <div><span>Default shift</span><strong>{employeeInsight.employee.shift_name || '-'}</strong></div>
                      <div><span>Created by</span><strong>{employeeInsight.employee.created_by_name || 'System'}</strong></div>
                    </div>
                    <DataTable
                      columns={['Type', 'App', 'Window', 'Duration', 'Start']}
                      rows={employeeInsight.recent_activity.map((row) => [
                        row.type,
                        row.app_name || '-',
                        row.window_title || '-',
                        secondsToHours(row.duration),
                        row.start_time ? new Date(row.start_time).toLocaleString() : '-',
                      ])}
                      emptyMessage="No activity recorded for this employee yet."
                    />
                    <DataTable
                      columns={['When', 'Change', 'Field', 'Old', 'New', 'Changed by']}
                      rows={(employeeInsight.history || []).map((row) => [
                        row.created_at ? new Date(row.created_at).toLocaleString() : '-',
                        row.change_type,
                        row.field_name || '-',
                        row.old_value || '-',
                        row.new_value || '-',
                        row.changed_by_name || 'System',
                      ])}
                      emptyMessage="No employee history has been recorded yet."
                    />
                  </div>
                ) : <EmptyState message={selectedEmployeeInsight ? 'Loading employee details...' : 'Select an employee from the workforce directory.'} />
              )}
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
