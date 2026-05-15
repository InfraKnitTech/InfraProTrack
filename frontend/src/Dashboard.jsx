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
const ANALYTICS_COLORS = {
  productive: '#2563eb',
  unproductive: '#059669',
  ideal: '#f59e0b',
};

function secondsToHours(seconds) {
  const totalSeconds = Math.max(0, Number(seconds) || 0);
  if (totalSeconds < 60) {
    return `${Math.round(totalSeconds)}s`;
  }
  if (totalSeconds < 3600) {
    const minutes = Math.max(1, Math.round(totalSeconds / 60));
    return `${minutes}m`;
  }
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.round((totalSeconds % 3600) / 60);
  return `${hours}h ${String(minutes).padStart(2, '0')}m`;
}

function scoreTone(score) {
  if (score >= 85) return 'good';
  if (score >= 75) return 'warn';
  return 'risk';
}

function analyticsCategory(category) {
  if (category === 'ideal' || category === 'idle') return 'ideal';
  if (category === 'unproductive' || category === 'prohibited') return 'unproductive';
  return 'productive';
}

function categoryLabel(category) {
  const normalized = analyticsCategory(category);
  if (normalized === 'ideal') return 'Ideal';
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function reportGroupLabel(groupBy) {
  if (groupBy === 'employee') return 'Employee';
  if (groupBy === 'manager') return 'Manager';
  if (groupBy === 'shift') return 'Shift time';
  return 'Project';
}

function formatIstDateTime(value) {
  if (!value) return '-';
  const text = String(value).trim();
  const cleaned = text.replace('T', ' ').replace('Z', '').replace(/\.\d+$/, '');
  const [datePart, timePart = ''] = cleaned.split(' ');
  const [year, month, day] = (datePart || '').split('-');
  const clock = timePart.slice(0, 8) || timePart;
  if (!year || !month || !day) return `${cleaned} IST`;
  return `${day}/${month}/${year}${clock ? `, ${clock}` : ''} IST`;
}

function excelSafe(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function downloadHtmlExcel(filename, sheetTitle, headers, rows) {
  const headerHtml = headers.map((header) => `<th>${excelSafe(header)}</th>`).join('');
  const bodyHtml = rows.map((row) => (
    `<tr>${row.map((cell) => `<td>${excelSafe(cell)}</td>`).join('')}</tr>`
  )).join('');
  const html = `
    <html>
      <head><meta charset="utf-8" /></head>
      <body>
        <table>
          <caption>${excelSafe(sheetTitle)}</caption>
          <thead><tr>${headerHtml}</tr></thead>
          <tbody>${bodyHtml}</tbody>
        </table>
      </body>
    </html>
  `;
  const blob = new Blob([html], { type: 'application/vnd.ms-excel;charset=utf-8;' });
  const objectUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(objectUrl);
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
    agent_id: '',
    username: '',
    full_name: '',
    email: '',
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

function blankProjectForm() {
  return {
    name: '',
    client_name: '',
    description: '',
    status: 'active',
    manager_id: '',
  };
}

function blankProjectTaskForm() {
  return {
    title: '',
    description: '',
    assignee_type: 'group',
    assignee_id: '',
    due_at: '',
    status: 'todo',
  };
}

function blankProjectRuleForm() {
  return {
    app_name: '',
    domain: '',
    category: 'productive',
    severity: 'medium',
  };
}

function employeeFormFromRecord(employee) {
  return {
    agent_id: '',
    username: employee.username || '',
    full_name: employee.full_name || '',
    email: employee.email || '',
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
  const employeeReportRequestRef = useRef(0);
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
  const [sessionEvents, setSessionEvents] = useState([]);
  const [activityRollup, setActivityRollup] = useState([]);
  const [productivityIndex, setProductivityIndex] = useState({ average_score: 0, employee_count: 0, rows: [] });
  const [productivityIndexLoading, setProductivityIndexLoading] = useState(false);
  const [analyticsGroupBy, setAnalyticsGroupBy] = useState('employee');
  const [analyticsSource, setAnalyticsSource] = useState('application');
  const [managerSummary, setManagerSummary] = useState([]);
  const [employeeSummary, setEmployeeSummary] = useState([]);
  const [employeeProductivityReport, setEmployeeProductivityReport] = useState([]);
  const [employeeReportGroupBy, setEmployeeReportGroupBy] = useState('project');
  const [employeeReportGroupSearch, setEmployeeReportGroupSearch] = useState('');
  const [employeeReportLoading, setEmployeeReportLoading] = useState(false);
  const [idleTimeReport, setIdleTimeReport] = useState([]);
  const [prohibitedUsageReport, setProhibitedUsageReport] = useState([]);
  const [reportExportTimezone, setReportExportTimezone] = useState('Asia/Kolkata');
  const [reportExportBusy, setReportExportBusy] = useState('');
  const [employees, setEmployees] = useState([]);
  const [pendingEmployeeAgents, setPendingEmployeeAgents] = useState([]);
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
  const [projects, setProjects] = useState([]);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [dashboardProjectId, setDashboardProjectId] = useState('');
  const [taskProjectId, setTaskProjectId] = useState('');
  const [projectDashboard, setProjectDashboard] = useState(null);
  const [taskProjectDashboard, setTaskProjectDashboard] = useState(null);
  const [projectForm, setProjectForm] = useState(blankProjectForm());
  const [projectTaskForm, setProjectTaskForm] = useState(blankProjectTaskForm());
  const [projectRuleForm, setProjectRuleForm] = useState(blankProjectRuleForm());
  const [groups, setGroups] = useState([]);
  const [groupsLoading, setGroupsLoading] = useState(false);
  const [groupOptions, setGroupOptions] = useState({ users: [], managers: [], projects: [], departments: [] });
  const [groupForm, setGroupForm] = useState({
    name: '',
    category_name: '',
    description: '',
    parent_group_id: '',
    leader_user_id: '',
    leader_title: '',
    members: [],
  });
  const [editingGroupId, setEditingGroupId] = useState(null);
  const [expandedGroupIds, setExpandedGroupIds] = useState([]);
  const [rules, setRules] = useState([]);
  const [rulesLoading, setRulesLoading] = useState(false);
  const [ruleFormFeedback, setRuleFormFeedback] = useState({ tone: '', message: '' });
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
    (groupOptions.departments || []).map((option) => option.label).filter(Boolean)
  ), [groupOptions.departments]);

  const designationOptions = useMemo(() => (
    [...new Set(employees.map((employee) => employee.designation).filter(Boolean))].sort()
  ), [employees]);
  const employeeReportGroupOptions = useMemo(() => {
    const reportOptions = employeeProductivityReport
      .filter((row) => row.group_by === employeeReportGroupBy)
      .map((row) => row.group_name)
      .filter(Boolean);
    const masterOptions = (() => {
      if (employeeReportGroupBy === 'employee') {
        return employees.map((employee) => employee.full_name || employee.username).filter(Boolean);
      }
      if (employeeReportGroupBy === 'manager') {
        return (groupOptions.managers || []).map((option) => option.label).filter(Boolean);
      }
      if (employeeReportGroupBy === 'shift') {
        return shifts.map((shift) => shift.name).filter(Boolean);
      }
      return projects.map((project) => project.name).filter(Boolean);
    })();
    return [...new Set([...masterOptions, ...reportOptions])]
      .sort((a, b) => a.localeCompare(b));
  }, [employeeProductivityReport, employeeReportGroupBy, employees, groupOptions.managers, projects, shifts]);
  const filteredEmployeeProductivityReport = useMemo(() => {
    const needle = employeeReportGroupSearch.trim().toLowerCase();
    if (!needle) {
      return employeeProductivityReport;
    }
    return employeeProductivityReport.filter((row) => (
      String(row.group_name || '').toLowerCase().includes(needle)
    ));
  }, [employeeProductivityReport, employeeReportGroupSearch]);

  const editableParentGroups = useMemo(() => (
    groups.filter((group) => group.id !== editingGroupId)
  ), [groups, editingGroupId]);

  const dashboardProject = useMemo(() => (
    projects.find((project) => String(project.id) === String(dashboardProjectId)) || null
  ), [projects, dashboardProjectId]);

  const taskProject = useMemo(() => (
    projects.find((project) => String(project.id) === String(taskProjectId)) || null
  ), [projects, taskProjectId]);

  const projectScopedRules = useMemo(() => (
    rules.filter((rule) => String(rule.project_id || '') === String(dashboardProjectId || ''))
  ), [rules, dashboardProjectId]);

  const projectTaskAssigneeOptions = useMemo(() => {
    if (projectTaskForm.assignee_type === 'manager') return groupOptions.managers || [];
    if (projectTaskForm.assignee_type === 'employee') return groupOptions.users || [];
    return groups.map((group) => ({ id: `group:${group.id}`, label: group.name, ref_id: group.id }));
  }, [projectTaskForm.assignee_type, groupOptions.managers, groupOptions.users, groups]);

  const analyticsTotals = useMemo(() => (
    activityRollup.reduce((acc, row) => ({
      productive: acc.productive + Number(row.productive_seconds || 0),
      unproductive: acc.unproductive + Number(row.unproductive_seconds || 0),
      ideal: acc.ideal + Number(row.idle_seconds || 0),
      total: acc.total + Number(row.total_seconds || 0),
    }), { productive: 0, unproductive: 0, ideal: 0, total: 0 })
  ), [activityRollup]);

  const analyticsPie = useMemo(() => [
    { name: 'Productive', value: analyticsTotals.productive },
    { name: 'Unproductive', value: analyticsTotals.unproductive },
    { name: 'Ideal', value: analyticsTotals.ideal },
  ].filter((row) => row.value > 0), [analyticsTotals]);

  const rollupChartData = useMemo(() => (
    activityRollup.slice(0, 8).map((row) => ({
      name: row.group_name,
      productive: Math.round((row.productive_seconds || 0) / 60),
      unproductive: Math.round((row.unproductive_seconds || 0) / 60),
      ideal: Math.round((row.idle_seconds || 0) / 60),
    }))
  ), [activityRollup]);

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
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const requests = [
        ['dashboard', axios.get(`${API_BASE}/api/dashboard/admin`, { headers })],
        ['apps', axios.get(`${API_BASE}/api/analytics/top-apps`, { headers })],
        ['domains', axios.get(`${API_BASE}/api/analytics/top-domains`, { headers })],
        ['sessions', axios.get(`${API_BASE}/api/analytics/session-events`, { headers })],
        ['manager', axios.get(`${API_BASE}/api/reports/productivity-summary`, { headers, params: { group_by: 'manager' } })],
        ['employee', axios.get(`${API_BASE}/api/reports/productivity-summary`, { headers, params: { group_by: 'employee' } })],
        ['shift', axios.get(`${API_BASE}/api/reports/productivity-summary`, { headers, params: { group_by: 'shift' } })],
        ['project', axios.get(`${API_BASE}/api/reports/productivity-summary`, { headers, params: { group_by: 'project' } })],
      ];
      const results = await Promise.allSettled(requests.map(([, request]) => request));
      results.forEach((result, index) => {
        const key = requests[index][0];
        if (result.status !== 'fulfilled') {
          if (!handleAuthError(result.reason)) {
            console.error(`Failed to fetch ${key} dashboard data`, result.reason);
          }
          return;
        }
        const data = result.value.data;
        if (key === 'dashboard') {
          setMetrics(data.metrics);
          setProductivityData(data.productivity_data || []);
        } else if (key === 'apps') {
          setAppUsageData(data.items || []);
        } else if (key === 'domains') {
          setTopDomains(data.items || []);
        } else if (key === 'sessions') {
          setSessionEvents(data.items || []);
        } else if (key === 'manager') {
          setManagerSummary(data.rows || []);
        } else if (key === 'employee') {
          setEmployeeSummary(data.rows || []);
        } else if (key === 'shift') {
          setShiftSummary(data.rows || []);
        } else if (key === 'project') {
          setProjectSummary(data.rows || []);
        }
      });
    };
    if (!['overview', 'managers', 'settings'].includes(activeTab)) {
      return undefined;
    }
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [activeTab]);

  const fetchDetailedAnalytics = async () => {
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const rollupRes = await axios.get(`${API_BASE}/api/analytics/activity-rollup`, {
        headers,
        params: {
          group_by: analyticsGroupBy,
          source: analyticsSource,
          limit: 100,
        },
      });
      setActivityRollup(rollupRes.data.items || []);
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to fetch detailed analytics', err);
    }
  };

  const fetchProductivityIndex = async () => {
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const res = await axios.get(`${API_BASE}/api/productivity-index/summary`, { headers });
      setProductivityIndex(res.data || { average_score: 0, employee_count: 0, rows: [] });
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to fetch productivity index', err);
    }
  };

  const recalculateProductivityIndex = async () => {
    try {
      setProductivityIndexLoading(true);
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const res = await axios.post(`${API_BASE}/api/productivity-index/recalculate`, {}, { headers });
      const rows = res.data.rows || [];
      const average = rows.length
        ? Math.round((rows.reduce((total, row) => total + Number(row.score || 0), 0) / rows.length) * 100) / 100
        : 0;
      setProductivityIndex({ average_score: average, employee_count: rows.length, rows });
      fetchEmployeeProductivityReport();
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to recalculate productivity index', err);
    } finally {
      setProductivityIndexLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab !== 'analytics') {
      return undefined;
    }
    fetchDetailedAnalytics();
    fetchProductivityIndex();
    const interval = setInterval(fetchDetailedAnalytics, 10000);
    return () => clearInterval(interval);
  }, [activeTab, analyticsGroupBy, analyticsSource]);

  const fetchEmployeeProductivityReport = async () => {
    const requestId = employeeReportRequestRef.current + 1;
    employeeReportRequestRef.current = requestId;
    const groupBy = employeeReportGroupBy;
    try {
      setEmployeeReportLoading(true);
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const summaryRes = await axios.get(`${API_BASE}/api/reports/employee-productivity-summary`, {
        headers,
        params: { group_by: groupBy },
      });
      if (requestId !== employeeReportRequestRef.current || groupBy !== employeeReportGroupBy) {
        return;
      }
      setEmployeeProductivityReport(summaryRes.data.rows || []);
      setEmployeeReportLoading(false);

      const [idleRes, prohibitedRes] = await Promise.allSettled([
        axios.get(`${API_BASE}/api/reports/idle-time`, { headers }),
        axios.get(`${API_BASE}/api/reports/prohibited-usage`, { headers }),
      ]);
      if (idleRes.status === 'fulfilled') {
        setIdleTimeReport(idleRes.value.data.rows || []);
      } else if (!handleAuthError(idleRes.reason)) {
        console.error('Failed to fetch idle time report', idleRes.reason);
      }
      if (prohibitedRes.status === 'fulfilled') {
        setProhibitedUsageReport(prohibitedRes.value.data.rows || []);
      } else if (!handleAuthError(prohibitedRes.reason)) {
        console.error('Failed to fetch prohibited usage report', prohibitedRes.reason);
      }
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to fetch employee productivity report', err);
      setEmployeeProductivityReport([]);
    } finally {
      if (requestId === employeeReportRequestRef.current) {
        setEmployeeReportLoading(false);
      }
    }
  };

  useEffect(() => {
    if (activeTab !== 'reports') {
      return;
    }
    fetchEmployeeProductivityReport();
  }, [activeTab, employeeReportGroupBy]);

  const downloadExcelReport = async (endpoint, filename) => {
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      setReportExportBusy(endpoint);
      const response = await axios.get(`${API_BASE}${endpoint}`, {
        headers,
        params: { report_timezone: reportExportTimezone },
        responseType: 'blob',
      });
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const objectUrl = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(objectUrl);
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to download Excel report', err);
    } finally {
      setReportExportBusy('');
    }
  };

  const downloadEmployeeProductivitySummaryTable = () => {
    const groupLabel = reportGroupLabel(employeeReportGroupBy);
    const suffix = employeeReportGroupSearch.trim()
      ? employeeReportGroupSearch.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
      : 'all';
    downloadHtmlExcel(
      `employee-productivity-summary-${employeeReportGroupBy}-${suffix || 'all'}.xls`,
      `Employee Productivity Summary by ${groupLabel}`,
      ['Group', 'Employee', 'Username', 'Login', 'Logout', 'Active', 'Productive', 'Idle', 'Productivity Score'],
      filteredEmployeeProductivityReport.map((row) => [
        row.group_name,
        row.employee_name,
        row.username,
        formatIstDateTime(row.login_time),
        formatIstDateTime(row.logout_time),
        secondsToHours(row.active_seconds),
        secondsToHours(row.productive_seconds),
        secondsToHours(row.idle_seconds),
        row.productivity_score ?? '-',
      ])
    );
  };

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
    const fallbackOptions = { users: [], managers: [], projects: [], departments: [] };
    try {
      setGroupsLoading(true);
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const groupsRes = await axios.get(`${API_BASE}/api/groups`, { headers });
      setGroups(groupsRes.data.items || []);
      try {
        const optionsRes = await axios.get(`${API_BASE}/api/groups/options`, { headers });
        setGroupOptions(optionsRes.data || fallbackOptions);
      } catch (optionsErr) {
        if (!handleAuthError(optionsErr)) {
          console.error('Failed to fetch group options', optionsErr);
          setGroupOptions(fallbackOptions);
        }
      }
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to fetch groups', err);
    } finally {
      setGroupsLoading(false);
    }
  };

  const fetchProjects = async () => {
    try {
      setProjectsLoading(true);
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const res = await axios.get(`${API_BASE}/api/projects`, { headers });
      const items = res.data.items || [];
      setProjects(items);
      const firstProjectId = items[0]?.id ? String(items[0].id) : '';
      setDashboardProjectId((current) => current || firstProjectId);
      setTaskProjectId((current) => current || firstProjectId);
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to fetch projects', err);
    } finally {
      setProjectsLoading(false);
    }
  };

  const fetchProjectDashboard = async (projectId = dashboardProjectId, target = 'dashboard') => {
    if (!projectId) {
      if (target === 'task') {
        setTaskProjectDashboard(null);
      } else {
        setProjectDashboard(null);
      }
      return;
    }
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const res = await axios.get(`${API_BASE}/api/projects/${projectId}/dashboard`, { headers });
      if (target === 'task') {
        setTaskProjectDashboard(res.data);
      } else {
        setProjectDashboard(res.data);
      }
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to fetch project dashboard', err);
      if (target === 'task') {
        setTaskProjectDashboard(null);
      } else {
        setProjectDashboard(null);
      }
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
      const employeesRes = await axios.get(`${API_BASE}/api/employees`, { headers, params });
      setEmployees(employeesRes.data.items || []);
      try {
        const shiftsRes = await axios.get(`${API_BASE}/api/shifts`, { headers });
        setShifts(shiftsRes.data.items || []);
      } catch (shiftErr) {
        if (!handleAuthError(shiftErr)) {
          console.error('Failed to fetch shifts for employee directory', shiftErr);
        }
      }
      fetchPendingEmployeeAgents(headers);
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to fetch employees and shifts', err);
    }
  };

  const fetchPendingEmployeeAgents = async (headersOverride = null) => {
    try {
      const headers = headersOverride || getAuthHeaders();
      if (!headers) {
        return;
      }
      const res = await axios.get(`${API_BASE}/api/employees/pending-agents`, { headers });
      setPendingEmployeeAgents(res.data.items || []);
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to fetch pending employee agents', err);
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
    fetchProjects();
  }, []);

  useEffect(() => {
    fetchProjectDashboard(dashboardProjectId, 'dashboard');
  }, [dashboardProjectId]);

  useEffect(() => {
    fetchProjectDashboard(taskProjectId, 'task');
  }, [taskProjectId]);

  useEffect(() => {
    fetchEmployeeDirectory();
  }, [employeeFilters]);

  useEffect(() => {
    if (activeTab === 'groups') {
      fetchGroups();
    }
    if (activeTab === 'projects') {
      fetchProjects();
    }
    if (activeTab === 'employees') {
      fetchEmployeeDirectory();
    }
    if (activeTab === 'reports') {
      fetchEmployeeDirectory();
      fetchGroups();
      fetchProjects();
    }
  }, [activeTab]);

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
      fetchPendingEmployeeAgents(headers);
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
    if (ruleFormFeedback.message) {
      setRuleFormFeedback({ tone: '', message: '' });
    }
  };

  const createRule = async (event) => {
    event.preventDefault();
    const payload = {
      ...ruleForm,
      app_name: ruleForm.app_name.trim(),
      domain: ruleForm.domain.trim(),
    };
    if (!payload.app_name && !payload.domain) {
      setRuleFormFeedback({ tone: 'error', message: 'Enter an application or domain before adding a rule.' });
      return;
    }
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      await axios.post(`${API_BASE}/api/rules`, payload, {
        headers,
      });
      setRuleForm({
        app_name: '',
        domain: '',
        category: 'productive',
        severity: 'medium',
      });
      setRuleFormFeedback({ tone: 'success', message: 'Rule added.' });
      fetchRules();
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      const detail = err.response?.data?.detail;
      const message = typeof detail === 'string'
        ? detail
        : err.response?.status === 503
          ? 'Database connection unavailable. Retry after MySQL is reachable.'
          : 'Rule could not be created. Check backend connectivity and try again.';
      setRuleFormFeedback({ tone: 'error', message });
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

  const handleProjectFormChange = (event) => {
    const { name, value } = event.target;
    setProjectForm((current) => ({ ...current, [name]: value }));
  };

  const createProject = async (event) => {
    event.preventDefault();
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const payload = {
        ...projectForm,
        manager_id: projectForm.manager_id ? Number(projectForm.manager_id) : null,
      };
      const res = await axios.post(`${API_BASE}/api/projects`, payload, { headers });
      setProjectForm(blankProjectForm());
      setDashboardProjectId((current) => current || String(res.data.id));
      setTaskProjectId((current) => current || String(res.data.id));
      fetchProjects();
      fetchGroups();
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to create project', err);
    }
  };

  const handleProjectTaskChange = (event) => {
    const { name, value } = event.target;
    setProjectTaskForm((current) => ({
      ...current,
      [name]: value,
      ...(name === 'assignee_type' ? { assignee_id: '' } : {}),
    }));
  };

  const createProjectTask = async (event) => {
    event.preventDefault();
    if (!taskProjectId) {
      return;
    }
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      const targetId = projectTaskForm.assignee_id ? Number(projectTaskForm.assignee_id) : null;
      const payload = {
        title: projectTaskForm.title,
        description: projectTaskForm.description || null,
        assignee_type: projectTaskForm.assignee_type,
        group_id: projectTaskForm.assignee_type === 'group' ? targetId : null,
        manager_user_id: projectTaskForm.assignee_type === 'manager' ? targetId : null,
        employee_user_id: projectTaskForm.assignee_type === 'employee' ? targetId : null,
        due_at: projectTaskForm.due_at || null,
        status: projectTaskForm.status,
      };
      await axios.post(`${API_BASE}/api/projects/${taskProjectId}/tasks`, payload, { headers });
      setProjectTaskForm(blankProjectTaskForm());
      fetchProjectDashboard(taskProjectId, 'task');
      if (String(taskProjectId) === String(dashboardProjectId)) {
        fetchProjectDashboard(dashboardProjectId, 'dashboard');
      }
      fetchProjects();
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to create project task', err);
    }
  };

  const updateProjectTaskStatus = async (task, nextStatus) => {
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      await axios.put(`${API_BASE}/api/projects/${task.project_id}/tasks/${task.id}`, { status: nextStatus }, { headers });
      if (String(task.project_id) === String(taskProjectId)) {
        fetchProjectDashboard(task.project_id, 'task');
      }
      if (String(task.project_id) === String(dashboardProjectId)) {
        fetchProjectDashboard(task.project_id, 'dashboard');
      }
      fetchProjects();
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to update project task', err);
    }
  };

  const handleProjectRuleChange = (event) => {
    const { name, value } = event.target;
    setProjectRuleForm((current) => ({ ...current, [name]: value }));
  };

  const createProjectRule = async (event) => {
    event.preventDefault();
    if (!dashboardProjectId) {
      return;
    }
    try {
      const headers = getAuthHeaders();
      if (!headers) {
        return;
      }
      await axios.post(`${API_BASE}/api/rules`, {
        ...projectRuleForm,
        project_id: Number(dashboardProjectId),
      }, { headers });
      setProjectRuleForm(blankProjectRuleForm());
      fetchRules();
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      console.error('Failed to create project rule', err);
    }
  };

  const handleGroupFormChange = (event) => {
    const { name, value } = event.target;
    setGroupForm((current) => ({ ...current, [name]: value }));
  };

  const toggleGroupCard = (groupId) => {
    setExpandedGroupIds((current) => (
      current.includes(groupId)
        ? current.filter((id) => id !== groupId)
        : [...current, groupId]
    ));
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
        parent_group_id: groupForm.parent_group_id ? Number(groupForm.parent_group_id) : null,
        leader_user_id: groupForm.leader_user_id ? Number(groupForm.leader_user_id) : null,
        leader_title: groupForm.leader_title || null,
        members: groupForm.members
          .filter((member) => member.member_type === 'department' ? member.department_name : member.ref_id)
          .map((member, index) => ({
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
      parent_group_id: group.parent_group_id || '',
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
      parent_group_id: '',
      leader_user_id: '',
      leader_title: '',
      members: [],
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
      if (employeeForm.department && !departmentOptions.includes(employeeForm.department)) {
        alert('Select a department from the Groups tab before saving the employee.');
        return;
      }
      const payload = {
        ...employeeForm,
        manager_id: employeeForm.manager_id ? Number(employeeForm.manager_id) : null,
        project_id: employeeForm.project_id ? Number(employeeForm.project_id) : null,
        shift_id: employeeForm.shift_id ? Number(employeeForm.shift_id) : null,
        assets: employeeForm.assets.filter((asset) => asset.asset_name.trim()),
        schedule: employeeForm.schedule,
        agent_id: employeeForm.agent_id ? Number(employeeForm.agent_id) : null,
      };
      if (editingEmployeeId) {
        delete payload.agent_id;
        await axios.put(`${API_BASE}/api/employees/${editingEmployeeId}`, payload, { headers });
      } else {
        await axios.post(`${API_BASE}/api/employees`, payload, { headers });
      }
      resetEmployeeForm();
      fetchEmployeeDirectory();
      fetchPendingEmployeeAgents();
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

  const startEmployeeFromAgent = (agent) => {
    setEditingEmployeeId(null);
    setEmployeeForm({
      ...blankEmployeeForm(),
      agent_id: agent.agent_id,
      username: agent.suggested_username || '',
      full_name: agent.suggested_full_name || agent.hostname || '',
      email: agent.suggested_email || '',
    });
    setEmployeeSubTab('form');
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
    ['projects', Briefcase, 'Projects'],
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
                      <small>
                        {agent.request_type === 'reregistration'
                          ? `Existing agent #${agent.agent_id} is trying to re-register`
                          : `${agent.os_type} - ${agent.username || 'unknown user'}`}
                      </small>
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

            <div className="panel full">
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
              <PanelHeader icon={LogOut} title="Login / Logout Trail" action="Recent" />
              <DataTable
                columns={['Employee', 'Event', 'Time']}
                rows={sessionEvents.slice(0, 6).map((row) => [
                  <div className="stacked-cell">
                    <strong>{row.employee_name}</strong>
                    <small>{row.department || row.project_name || row.username}</small>
                  </div>,
                  <span className={`status-pill session-${row.event_type}`}>{row.event_type}</span>,
                  formatIstDateTime(row.captured_at),
                ])}
                emptyMessage="No login or logout events captured yet."
              />
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

            <div className="panel full">
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
                      <span>Parent group</span>
                      <select className="input-field" name="parent_group_id" value={groupForm.parent_group_id} onChange={handleGroupFormChange}>
                        <option value="">Root group</option>
                        {editableParentGroups.map((group) => (
                          <option key={group.id} value={group.id}>
                            {group.name} ({group.category_name})
                          </option>
                        ))}
                      </select>
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
                    {groupForm.members.length ? (
                      groupForm.members.map((member, index) => (
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
                      ))
                    ) : (
                      <div className="empty-state compact">No members yet. Create the group first or add members later.</div>
                    )}
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
                columns={['Parent', 'Category', 'Group', 'Leader', 'Employees', 'Productive', 'Active', 'Idle', 'Productivity %', 'Members', 'Actions']}
                rows={groups.map((group) => [
                  group.parent_group_name || 'Root',
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
              <PanelHeader icon={Users} title="All Group Hierarchy" action="Root groups and nested children" />
              {groups.length ? (
                <div className="group-tree">
                  <AllGroupHierarchy groups={groups} />
                </div>
              ) : <EmptyState message="No group hierarchy exists yet." />}
            </div>

            <div className="panel full">
              <PanelHeader icon={Users} title="Group Hierarchies" action="Click a group to inspect its members" />
              {groups.length ? (
                <div className="group-cards">
                  {groups.map((group) => (
                    <div className="group-card" key={group.id}>
                      <div className="group-card-head">
                        <div>
                          <strong>{group.name}</strong>
                          <small>{group.category_name}</small>
                        </div>
                        <div className="group-card-head-actions">
                          <div className="group-chip-row">
                            {group.parent_group_name && <span className="status-pill">Parent: {group.parent_group_name}</span>}
                            {group.leader_name && <span className="status-pill">{group.leader_name}{group.leader_title ? ` - ${group.leader_title}` : ''}</span>}
                            <span className="status-pill">{group.summary.employee_count} people</span>
                            <span className={`score ${scoreTone(Math.round(group.summary.productivity_percent))}`}>{Math.round(group.summary.productivity_percent)}%</span>
                          </div>
                          <button className="btn btn-secondary" onClick={() => toggleGroupCard(group.id)}>
                            {expandedGroupIds.includes(group.id) ? 'Close' : 'Open'}
                          </button>
                        </div>
                      </div>
                      {expandedGroupIds.includes(group.id) && (
                        <>
                          {group.description && <p>{group.description}</p>}
                          <GroupHierarchy members={group.members} />
                        </>
                      )}
                    </div>
                  ))}
                </div>
              ) : <EmptyState message="No live custom group hierarchy exists yet." />}
            </div>
          </section>
        )}

        {activeTab === 'projects' && (
          <section className="page-grid">
            <div className="panel full">
              <PanelHeader icon={Briefcase} title="Project Control Center" action="Assignments and timelines" />
              <div className="project-layout">
                <form className="project-form" onSubmit={createProject}>
                  <div className="group-form-grid">
                    <label>
                      <span>Project name</span>
                      <input className="input-field" name="name" value={projectForm.name} onChange={handleProjectFormChange} placeholder="AI Operations Migration" required />
                    </label>
                    <label>
                      <span>Client / owner</span>
                      <input className="input-field" name="client_name" value={projectForm.client_name} onChange={handleProjectFormChange} placeholder="Internal, client name, business unit" />
                    </label>
                    <label>
                      <span>Project manager</span>
                      <select className="input-field" name="manager_id" value={projectForm.manager_id} onChange={handleProjectFormChange}>
                        <option value="">No manager assigned</option>
                        {groupOptions.users.map((option) => (
                          <option key={option.id} value={option.ref_id}>{option.label}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Status</span>
                      <select className="input-field" name="status" value={projectForm.status} onChange={handleProjectFormChange}>
                        <option value="active">Active</option>
                        <option value="paused">Paused</option>
                        <option value="completed">Completed</option>
                        <option value="archived">Archived</option>
                      </select>
                    </label>
                    <label className="group-form-wide">
                      <span>Description</span>
                      <input className="input-field" name="description" value={projectForm.description} onChange={handleProjectFormChange} placeholder="Scope, delivery notes, or success criteria" />
                    </label>
                  </div>
                  <div className="group-builder-actions">
                    <button className="btn btn-primary" type="submit">
                      <Plus size={16} />
                      Create project
                    </button>
                  </div>
                </form>

                <DataTable
                  columns={['Project', 'Manager', 'Status', 'Employees', 'Open tasks', 'Productive', 'Idle', 'Productivity %']}
                  rows={projects.map((project) => [
                    <div className="stacked-cell">
                      <strong>{project.name}</strong>
                      <small>{project.client_name || project.description || 'No client set'}</small>
                    </div>,
                    project.manager_name || '-',
                    <span className={`status-pill project-${project.status}`}>{project.status}</span>,
                    project.summary.employee_count,
                    `${project.summary.open_task_count} / ${project.summary.task_count}`,
                    secondsToHours(project.summary.productive_seconds),
                    secondsToHours(project.summary.idle_seconds),
                    <span className={`score ${scoreTone(Math.round(project.summary.productivity_percent))}`}>{Math.round(project.summary.productivity_percent)}</span>,
                  ])}
                  emptyMessage={projectsLoading ? 'Loading projects...' : 'No projects created yet.'}
                />
              </div>
            </div>

            <div className="panel full">
              <PanelHeader icon={BarChart3} title="Project Dashboard" action={dashboardProject?.name || 'Select a project'} />
              {dashboardProject && projectDashboard ? (
                <div className="project-dashboard">
                  <div className="project-selector-row">
                    <select className="input-field" value={dashboardProjectId} onChange={(event) => setDashboardProjectId(event.target.value)}>
                      {projects.map((project) => (
                        <option key={project.id} value={project.id}>{project.name}</option>
                      ))}
                    </select>
                    <div className="project-kpi-strip">
                      <span>{projectDashboard.project.summary.employee_count} employees</span>
                      <span>{projectDashboard.project.summary.open_task_count} open tasks</span>
                      <span>{secondsToHours(projectDashboard.project.summary.productive_seconds)} productive</span>
                      <span>{Math.round(projectDashboard.project.summary.productivity_percent)}% score</span>
                    </div>
                  </div>

                  <div className="project-dashboard-stack">
                    <div>
                      <PanelHeader icon={Users} title="Manager Rollup" action="Drilldown" />
                      <DataTable
                        columns={['Manager', 'Employees', 'Productive', 'Unproductive', 'Idle', 'Productivity %']}
                        rows={projectDashboard.manager_rows.map((row) => [
                          row.name,
                          row.employee_count,
                          secondsToHours(row.productive_seconds),
                          secondsToHours(row.unproductive_seconds),
                          secondsToHours(row.idle_seconds),
                          <span className={`score ${scoreTone(Math.round(row.productivity_percent))}`}>{Math.round(row.productivity_percent)}</span>,
                        ])}
                        emptyMessage="No manager-wise activity for this project yet."
                      />
                    </div>
                    <div>
                      <PanelHeader icon={User} title="Employee Drilldown" action="Per person" />
                      <DataTable
                        columns={['Employee', 'Productive', 'Unproductive', 'Idle', 'Productivity %']}
                        rows={projectDashboard.employee_rows.map((row) => [
                          row.name,
                          secondsToHours(row.productive_seconds),
                          secondsToHours(row.unproductive_seconds),
                          secondsToHours(row.idle_seconds),
                          <span className={`score ${scoreTone(Math.round(row.productivity_percent))}`}>{Math.round(row.productivity_percent)}</span>,
                        ])}
                        emptyMessage="No employee activity for this project yet."
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <EmptyState message="Select or create a project to view manager and employee drilldowns." />
              )}
            </div>

            <div className="panel full task-assignment-panel">
              <PanelHeader icon={CalendarDays} title="Task Assignment" action="Group, manager, or employee" />
              {taskProject ? (
                <div className="task-workbench">
                  <div className="project-selector-row task-project-selector">
                    <label>
                      <span>Project</span>
                      <select className="input-field" value={taskProjectId} onChange={(event) => setTaskProjectId(event.target.value)}>
                        {projects.map((project) => (
                          <option key={project.id} value={project.id}>{project.name}</option>
                        ))}
                      </select>
                    </label>
                    <div className="project-kpi-strip">
                      <span>{taskProjectDashboard?.project?.summary?.open_task_count || 0} open tasks</span>
                      <span>{taskProjectDashboard?.project?.summary?.employee_count || 0} people in scope</span>
                    </div>
                  </div>
                  <form className="task-composer" onSubmit={createProjectTask}>
                    <div className="task-composer-head">
                      <div>
                        <strong>Create assignment</strong>
                        <small>{taskProject.name}</small>
                      </div>
                    </div>
                    <div className="task-form-grid">
                      <label className="task-title-field">
                        <span>Task</span>
                        <input className="input-field" name="title" value={projectTaskForm.title} onChange={handleProjectTaskChange} placeholder="Complete endpoint validation" required />
                      </label>
                      <label>
                        <span>Assign to</span>
                        <select className="input-field" name="assignee_type" value={projectTaskForm.assignee_type} onChange={handleProjectTaskChange}>
                          <option value="group">Group</option>
                          <option value="manager">Manager</option>
                          <option value="employee">Employee</option>
                        </select>
                      </label>
                      <label>
                        <span>Assignee</span>
                        <select className="input-field" name="assignee_id" value={projectTaskForm.assignee_id} onChange={handleProjectTaskChange} required>
                          <option value="">Select assignee</option>
                          {projectTaskAssigneeOptions.map((option) => (
                            <option key={option.id} value={option.ref_id}>{option.label}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        <span>Due timeline</span>
                        <input className="input-field" type="datetime-local" name="due_at" value={projectTaskForm.due_at} onChange={handleProjectTaskChange} />
                      </label>
                      <label>
                        <span>Status</span>
                        <select className="input-field" name="status" value={projectTaskForm.status} onChange={handleProjectTaskChange}>
                          <option value="todo">To do</option>
                          <option value="in_progress">In progress</option>
                          <option value="blocked">Blocked</option>
                          <option value="completed">Completed</option>
                        </select>
                      </label>
                      <label className="task-description-field">
                        <span>Description</span>
                        <input className="input-field" name="description" value={projectTaskForm.description} onChange={handleProjectTaskChange} placeholder="Acceptance criteria or delivery notes" />
                      </label>
                      <div className="task-submit-cell">
                        <button className="btn btn-primary" type="submit">
                          <Plus size={16} />
                          Assign task
                        </button>
                      </div>
                    </div>
                  </form>

                  <div className="task-board">
                    <div className="task-board-head">
                      <div>
                        <strong>Assigned work</strong>
                        <small>Timeline, owner, and live status</small>
                      </div>
                      <span className="status-pill">{taskProjectDashboard?.tasks?.length || 0} tasks</span>
                    </div>
                    <DataTable
                      columns={['Task', 'Assigned to', 'Due', 'Status', 'Update']}
                      rows={(taskProjectDashboard?.tasks || []).map((task) => [
                        <div className="stacked-cell">
                          <strong>{task.title}</strong>
                          <small>{task.description || task.assignee_type}</small>
                        </div>,
                        task.assignee_label,
                        formatIstDateTime(task.due_at),
                        <span className={`status-pill task-${task.status}`}>{task.status.replace('_', ' ')}</span>,
                        <select className="input-field compact-select" value={task.status} onChange={(event) => updateProjectTaskStatus(task, event.target.value)}>
                          <option value="todo">To do</option>
                          <option value="in_progress">In progress</option>
                          <option value="blocked">Blocked</option>
                          <option value="completed">Completed</option>
                        </select>,
                      ])}
                      emptyMessage="No tasks assigned to this project yet."
                    />
                  </div>
                </div>
              ) : (
                <EmptyState message="Create a project before assigning tasks." />
              )}
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
                      <button className="btn btn-secondary" onClick={() => setEmployeeSubTab('pending-agents')}>
                        <ShieldCheck size={16} />
                        Pending employees {pendingEmployeeAgents.length > 0 ? `(${pendingEmployeeAgents.length})` : ''}
                      </button>
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

              {employeeSubTab === 'pending-agents' && (
                <>
                  <div className="module-header">
                    <div>
                      <ShieldCheck size={18} />
                      <div>
                        <h2>Pending Employee Confirmations</h2>
                        <p>Registered agents waiting for employee profile completion</p>
                      </div>
                    </div>
                    <button className="btn btn-secondary" onClick={() => setEmployeeSubTab('directory')}>Back to workforce</button>
                  </div>
                  <DataTable
                    columns={['Device', 'Suggested employee', 'Agent user', 'OS', 'IP', 'Last seen', 'Status', 'Action']}
                    rows={pendingEmployeeAgents.map((agent) => [
                      agent.hostname,
                      <div className="stacked-cell">
                        <strong>{agent.suggested_full_name}</strong>
                        <small>{agent.suggested_email}</small>
                      </div>,
                      agent.username || '-',
                      `${agent.os_type}${agent.os_version ? ` ${agent.os_version}` : ''}`,
                      agent.ip_address || '-',
                      formatIstDateTime(agent.last_seen_at),
                      <span className="status-pill">{agent.status}</span>,
                      <button className="btn btn-primary compact" onClick={() => startEmployeeFromAgent(agent)}>
                        <UserPlus size={15} />
                        Complete
                      </button>,
                    ])}
                    emptyMessage="No registered agents are waiting for employee confirmation."
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
                    {employeeForm.agent_id && (
                      <div className="linked-agent-banner">
                        <ShieldCheck size={17} />
                        <div>
                          <strong>Agent token will be linked to this employee</strong>
                          <small>Complete the missing profile, assignment, project, and shift details before creating the employee.</small>
                        </div>
                      </div>
                    )}
                    <div className="employee-form-grid">
                      <label><span>Full name</span><input className="input-field" name="full_name" value={employeeForm.full_name} onChange={handleEmployeeChange} required /></label>
                      <label><span>Username</span><input className="input-field" name="username" value={employeeForm.username} onChange={handleEmployeeChange} required /></label>
                      <label><span>Email</span><input className="input-field" type="email" name="email" value={employeeForm.email} onChange={handleEmployeeChange} required /></label>
                      <label><span>Employee code</span><input className="input-field" name="employee_code" value={employeeForm.employee_code} onChange={handleEmployeeChange} /></label>
                      <label>
                        <span>Department / Team</span>
                        <input
                          className="input-field"
                          name="department"
                          list="employee-department-options"
                          value={employeeForm.department}
                          onChange={handleEmployeeChange}
                          placeholder="Search a group from Groups tab"
                        />
                        <small className="field-hint">Choose from an existing group, department, team, or category.</small>
                      </label>
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
                  <datalist id="employee-department-options">
                    {departmentOptions.map((department) => (
                      <option key={department} value={department} />
                    ))}
                  </datalist>
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
                      columns={['Type', 'App', 'Window', 'URL', 'Duration', 'Start', 'End']}
                      rows={employeeInsight.recent_activity.map((row) => [
                        row.type,
                        row.app_name || '-',
                        <span className="truncate-cell app-window" title={row.window_title || '-'}>
                          {row.window_title || '-'}
                        </span>,
                        row.url ? (
                          <span className="truncate-cell url-cell" title={row.url}>
                            {row.url}
                          </span>
                        ) : '-',
                        secondsToHours(row.duration),
                        formatIstDateTime(row.start_time),
                        formatIstDateTime(row.end_time),
                      ])}
                      emptyMessage="No activity recorded for this employee yet."
                    />
                    <DataTable
                      columns={['When', 'Change', 'Field', 'Old', 'New', 'Changed by']}
                      rows={(employeeInsight.history || []).map((row) => [
                        formatIstDateTime(row.created_at),
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
            <div className="metric-card accent-blue">
              <span>Productive</span>
              <strong>{secondsToHours(analyticsTotals.productive)}</strong>
              <small>Selected analytics scope</small>
            </div>
            <div className="metric-card accent-red">
              <span>Unproductive</span>
              <strong>{secondsToHours(analyticsTotals.unproductive)}</strong>
              <small>Rules and known distractions</small>
            </div>
            <div className="metric-card accent-amber">
              <span>Ideal</span>
              <strong>{secondsToHours(analyticsTotals.ideal)}</strong>
              <small>No active work detected</small>
            </div>
            <div className="metric-card accent-green">
              <span>Productivity</span>
              <strong>{analyticsTotals.total ? Math.round((analyticsTotals.productive / analyticsTotals.total) * 100) : 0}%</strong>
              <small>Productive / total tracked</small>
            </div>

            <div className="panel full">
              <PanelHeader icon={BarChart3} title="Productivity Drilldown" action="Employee, manager, department, project" />
              <div className="analytics-controls">
                <label>
                  <span>Group by</span>
                  <select className="input-field" value={analyticsGroupBy} onChange={(event) => setAnalyticsGroupBy(event.target.value)}>
                    <option value="employee">Employee</option>
                    <option value="manager">Manager</option>
                    <option value="department">Team / Department</option>
                    <option value="project">Project</option>
                  </select>
                </label>
                <label>
                  <span>Source</span>
                  <select className="input-field" value={analyticsSource} onChange={(event) => setAnalyticsSource(event.target.value)}>
                    <option value="application">Applications</option>
                    <option value="browser">Browser URLs</option>
                    <option value="all">Applications + URLs</option>
                  </select>
                </label>
                <button className="btn btn-secondary" onClick={fetchDetailedAnalytics}>
                  <RefreshCw size={16} />
                  Refresh
                </button>
              </div>
              <div className="analytics-chart-grid">
                <div className="chart-card">
                  <PanelHeader icon={BarChart3} title="Scope Comparison" action="Minutes" />
                  {rollupChartData.length ? (
                    <div className="chart-md">
                      <ResponsiveContainer>
                        <BarChart data={rollupChartData}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} />
                          <XAxis dataKey="name" />
                          <YAxis />
                          <Tooltip />
                          <Bar dataKey="productive" fill={ANALYTICS_COLORS.productive} radius={[3, 3, 0, 0]} />
                          <Bar dataKey="unproductive" fill={ANALYTICS_COLORS.unproductive} radius={[3, 3, 0, 0]} />
                          <Bar dataKey="ideal" fill={ANALYTICS_COLORS.ideal} radius={[3, 3, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : <EmptyState message="No scope chart data yet." />}
                </div>
                <div className="chart-card">
                  <PanelHeader icon={Activity} title="Work Mix" action="Live" />
                  {analyticsPie.length ? (
                    <div className="chart-md">
                      <ResponsiveContainer>
                        <PieChart>
                          <Pie data={analyticsPie} dataKey="value" innerRadius={54} outerRadius={82} paddingAngle={3}>
                            {analyticsPie.map((entry) => (
                              <Cell key={entry.name} fill={ANALYTICS_COLORS[entry.name.toLowerCase()] || COLORS[0]} />
                            ))}
                          </Pie>
                          <Tooltip formatter={(value) => secondsToHours(value)} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  ) : <EmptyState message="No work mix data yet." />}
                  <LegendList rows={analyticsPie} />
                </div>
              </div>
              <DataTable
                columns={['Scope', 'Productive', 'Unproductive', 'Ideal', 'Total', 'Productivity %']}
                rows={activityRollup.map((row) => [
                  row.group_name,
                  secondsToHours(row.productive_seconds),
                  secondsToHours(row.unproductive_seconds),
                  secondsToHours(row.idle_seconds),
                  secondsToHours(row.total_seconds),
                  <span className={`score ${scoreTone(Math.round(row.productivity_percent))}`}>{Math.round(row.productivity_percent)}</span>,
                ])}
                emptyMessage="No detailed productivity rollup available yet."
              />
            </div>

            <div className="panel wide">
              <PanelHeader icon={Activity} title="Application Analytics" action="Top usage" />
              <DataTable
                columns={['Application', 'Duration', 'Category']}
                rows={appChart.map((row) => [row.name, secondsToHours(row.value), categoryLabel(row.category)])}
                emptyMessage="No live application analytics yet."
              />
            </div>
            <div className="panel">
              <PanelHeader icon={Building2} title="Top Domains" action="Top 10" />
              <DataTable
                columns={['Domain', 'Duration', 'Category']}
                rows={domainChart.map((row) => [row.name, secondsToHours(row.value), categoryLabel(row.category)])}
                emptyMessage="No live domain usage data yet."
              />
            </div>
            <div className="panel full">
              <PanelHeader icon={BarChart3} title="Productivity Index Model" action="Stored DB scores" />
              <div className="analytics-controls">
                <div className="index-summary">
                  <span>Average score</span>
                  <strong>{Math.round(productivityIndex.average_score || 0)}</strong>
                  <small>{productivityIndex.employee_count || 0} employees scored</small>
                </div>
                <button className="btn btn-primary" onClick={recalculateProductivityIndex} disabled={productivityIndexLoading}>
                  <RefreshCw size={16} />
                  {productivityIndexLoading ? 'Calculating...' : 'Recalculate index'}
                </button>
              </div>
              <DataTable
                columns={['Employee', 'Score', 'Productive %', 'Unproductive %', 'Ideal %', 'Login', 'Logout', 'Date']}
                rows={(productivityIndex.rows || []).map((row) => [
                  <div className="stacked-cell">
                    <strong>{row.employee_name}</strong>
                    <small>{row.username}</small>
                  </div>,
                  <span className={`score ${scoreTone(Number(row.score || 0))}`}>{row.score}</span>,
                  `${row.productive_pct}%`,
                  `${row.unproductive_pct}%`,
                  `${row.idle_pct}%`,
                  formatIstDateTime(row.login_time),
                  formatIstDateTime(row.logout_time),
                  formatIstDateTime(row.date),
                ])}
                emptyMessage={productivityIndexLoading ? 'Calculating productivity index...' : 'No stored productivity scores yet. Click Recalculate index.'}
              />
            </div>
          </section>
        )}

        {activeTab === 'reports' && (
          <section className="page-grid">
            <div className="panel full">
              <PanelHeader icon={Download} title="Excel Productivity Exports" action="Downloadable .xlsx workbooks" />
              <div className="analytics-controls">
                <label>
                  <span>Export timezone</span>
                  <select className="input-field" value={reportExportTimezone} onChange={(event) => setReportExportTimezone(event.target.value)}>
                    <option value="Asia/Kolkata">Asia/Kolkata IST</option>
                    <option value="UTC">UTC</option>
                  </select>
                </label>
              </div>
              <div className="report-grid">
                <button
                  className="report-card"
                  onClick={() => downloadExcelReport('/api/reports/exports/manager-project-employee.xlsx', 'manager-project-employee-productivity.xlsx')}
                  disabled={reportExportBusy !== ''}
                >
                  <FileSpreadsheet size={24} />
                  <div>
                    <strong>Manager / Project / Employee</strong>
                    <small>Three productivity sheets in one workbook.</small>
                  </div>
                  <Download size={18} />
                </button>
                <button
                  className="report-card"
                  onClick={() => downloadExcelReport('/api/reports/exports/employee-comprehensive.xlsx', 'employee-comprehensive-productivity.xlsx')}
                  disabled={reportExportBusy !== ''}
                >
                  <Users size={24} />
                  <div>
                    <strong>Employee Comprehensive</strong>
                    <small>Durations, login/logout, manager, project, shift.</small>
                  </div>
                  <Download size={18} />
                </button>
                <button
                  className="report-card"
                  onClick={() => downloadExcelReport('/api/reports/exports/timezone-optimized.xlsx', `timezone-optimized-productivity-${reportExportTimezone.replace('/', '-')}.xlsx`)}
                  disabled={reportExportBusy !== ''}
                >
                  <Clock size={24} />
                  <div>
                    <strong>Timezone Optimized</strong>
                    <small>Converted timestamps plus idle-break detail sheet.</small>
                  </div>
                  <Download size={18} />
                </button>
              </div>
            </div>
            <div className="panel full">
              <PanelHeader icon={FileSpreadsheet} title="Employee Productivity Summary Report" action="Project, manager, and shift" />
              <div className="analytics-controls">
                <label>
                  <span>Group by</span>
                  <select
                    className="input-field"
                    value={employeeReportGroupBy}
                    onChange={(event) => {
                      setEmployeeReportGroupBy(event.target.value);
                      setEmployeeReportGroupSearch('');
                      setEmployeeProductivityReport([]);
                    }}
                  >
                    <option value="employee">Employee</option>
                    <option value="project">Project</option>
                    <option value="manager">Manager</option>
                    <option value="shift">Shift</option>
                  </select>
                </label>
                <label>
                  <span>Search {reportGroupLabel(employeeReportGroupBy)}</span>
                  <input
                    className="input-field"
                    list="employee-productivity-group-options"
                    value={employeeReportGroupSearch}
                    onChange={(event) => setEmployeeReportGroupSearch(event.target.value)}
                    placeholder={`All ${reportGroupLabel(employeeReportGroupBy).toLowerCase()}s`}
                  />
                  <datalist id="employee-productivity-group-options">
                    {employeeReportGroupOptions.map((option) => (
                      <option key={option} value={option} />
                    ))}
                  </datalist>
                </label>
                <button className="btn btn-secondary" onClick={fetchEmployeeProductivityReport}>
                  <RefreshCw size={16} />
                  Refresh
                </button>
                <button
                  className="btn btn-primary"
                  onClick={downloadEmployeeProductivitySummaryTable}
                  disabled={!filteredEmployeeProductivityReport.length}
                >
                  <Download size={16} />
                  Download
                </button>
              </div>
              <div className="fixed-table session-events-table">
                <DataTable
                  columns={['Group', 'Employee', 'Username', 'Login', 'Logout', 'Active', 'Productive', 'Idle', 'Score']}
                  rows={filteredEmployeeProductivityReport.map((row) => [
                    row.group_name,
                    row.employee_name,
                    row.username,
                    formatIstDateTime(row.login_time),
                    formatIstDateTime(row.logout_time),
                    secondsToHours(row.active_seconds),
                    secondsToHours(row.productive_seconds),
                    secondsToHours(row.idle_seconds),
                    row.productivity_score == null ? '-' : (
                      <span className={`score ${scoreTone(Number(row.productivity_score))}`}>{row.productivity_score}</span>
                    ),
                  ])}
                  emptyMessage={employeeReportLoading ? 'Loading employee productivity report...' : 'No employee productivity report data is available yet.'}
                />
              </div>
            </div>
            <div className="panel full">
              <PanelHeader icon={Clock} title="Idle Time Break Report" action="Reason capture" />
              <div className="fixed-table session-events-table">
                <DataTable
                  columns={['Employee', 'Project', 'Manager', 'Shift', 'Idle start', 'Idle end', 'Duration', 'Category', 'Reason']}
                  rows={idleTimeReport.map((row) => [
                    row.employee_name,
                    row.project_name || '-',
                    row.manager_name || '-',
                    row.shift_name || '-',
                    formatIstDateTime(row.start_time),
                    formatIstDateTime(row.end_time),
                    secondsToHours(row.duration),
                    row.reason_category || 'Pending',
                    row.reason || 'Pending employee reason',
                  ])}
                  emptyMessage="No idle time breaks have been captured yet."
                />
              </div>
            </div>
            <div className="panel full">
              <PanelHeader icon={AlertTriangle} title="Prohibited Application and Domain Usage" action="Manager email alerts" />
              <div className="fixed-table detailed-session-table">
                <DataTable
                  columns={['Employee', 'Project', 'Manager', 'Type', 'Resource', 'First seen', 'Last seen', 'Duration', 'Attempts', 'Email alert']}
                  rows={prohibitedUsageReport.map((row) => [
                    row.employee_name,
                    row.project_name || '-',
                    row.manager_name || '-',
                    row.resource_type,
                    <div className="stacked-cell">
                      <strong>{row.domain || row.app_name || '-'}</strong>
                      <small>{row.url || row.window_title || '-'}</small>
                    </div>,
                    formatIstDateTime(row.first_seen_at),
                    formatIstDateTime(row.last_seen_at),
                    secondsToHours(row.duration),
                    row.occurrence_count,
                    <div className="stacked-cell">
                      <span className={`status-pill alert-${row.email_status}`}>{row.email_status.replaceAll('_', ' ')}</span>
                      <small>{row.manager_email || row.email_error || 'No manager email'}</small>
                    </div>,
                  ])}
                  emptyMessage="No prohibited application or domain usage has been recorded yet."
                />
              </div>
            </div>
          </section>
        )}

        {activeTab === 'settings' && (
          <section className="page-grid">
            <div className="panel wide">
              <PanelHeader icon={Settings} title="App and URL Rules" action="Project scoped" />
              <div className="rules-layout">
                <form className="rule-form" onSubmit={createRule}>
                  {ruleFormFeedback.message && (
                    <div className={`inline-feedback ${ruleFormFeedback.tone}`}>
                      {ruleFormFeedback.message}
                    </div>
                  )}
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

function AllGroupHierarchy({ groups }) {
  const tree = useMemo(() => {
    const byParent = new Map();
    groups.forEach((group) => {
      const parentKey = group.parent_group_id || 0;
      const bucket = byParent.get(parentKey) || [];
      bucket.push(group);
      byParent.set(parentKey, bucket);
    });
    return byParent;
  }, [groups]);

  const renderBranch = (parentId = 0, depth = 0) => {
    const branch = tree.get(parentId) || [];
    return branch.map((group) => (
      <div className="group-tree-node" key={group.id} style={{ marginLeft: `${depth * 18}px` }}>
        <div className="group-tree-row">
          <strong>{group.name}</strong>
          <small>{group.category_name}</small>
          <span className="status-pill">{group.summary.employee_count} people</span>
          {group.leader_name && <span className="status-pill">{group.leader_name}</span>}
        </div>
        {renderBranch(group.id, depth + 1)}
      </div>
    ));
  };

  return <div className="group-tree">{renderBranch()}</div>;
}
