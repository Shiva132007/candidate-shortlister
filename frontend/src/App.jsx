import React, { useState, useEffect } from 'react';

// Custom inline Markdown parser for AI Chat bubbles
const parseInlineFormatting = (text) => {
  const parts = text.split('**');
  return parts.map((part, index) => {
    if (index % 2 === 1) {
      return <strong key={index} style={{ color: '#fff', fontWeight: 700 }}>{part}</strong>;
    }
    return part;
  });
};

const renderMarkdown = (text) => {
  if (!text) return null;
  const lines = text.split('\n');
  return lines.map((line, idx) => {
    if (line.startsWith('### ')) {
      return <h4 key={idx} style={{ fontSize: '13px', fontWeight: 'bold', color: '#fff', margin: '12px 0 6px 0' }}>{line.substring(4)}</h4>;
    }
    if (line.startsWith('## ')) {
      return <h3 key={idx} style={{ fontSize: '14px', fontWeight: 'bold', color: '#fff', margin: '14px 0 8px 0' }}>{line.substring(3)}</h3>;
    }
    if (line.startsWith('# ')) {
      return <h2 key={idx} style={{ fontSize: '16px', fontWeight: 'bold', color: '#fff', margin: '16px 0 10px 0' }}>{line.substring(2)}</h2>;
    }
    if (line.startsWith('- ') || line.startsWith('* ')) {
      return <li key={idx} style={{ marginLeft: '12px', listStyleType: 'disc', marginBottom: '4px' }}>{parseInlineFormatting(line.substring(2))}</li>;
    }
    if (/^\d+\.\s/.test(line)) {
      const content = line.replace(/^\d+\.\s/, '');
      return <li key={idx} style={{ marginLeft: '12px', listStyleType: 'decimal', marginBottom: '4px' }}>{parseInlineFormatting(content)}</li>;
    }
    if (line.startsWith('|')) {
      const cols = line.split('|').map(c => c.trim()).filter(c => c !== '');
      if (line.includes('---')) return null;
      return (
        <div key={idx} style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.05)', padding: '6px 0', fontSize: '10.5px' }}>
          {cols.map((col, cIdx) => (
            <span key={cIdx} style={{ flex: 1, padding: '2px 4px', fontWeight: line.includes('Parameter') ? 'bold' : 'normal' }}>
              {parseInlineFormatting(col)}
            </span>
          ))}
        </div>
      );
    }
    return <p key={idx} style={{ marginBottom: '8px' }}>{parseInlineFormatting(line)}</p>;
  });
};

// SVG Donut Chart Component
const DonutChart = ({ data }) => {
  const total = data.reduce((sum, item) => sum + item.value, 0);
  let accumulatedPercent = 0;
  
  return (
    <svg width="220" height="150" viewBox="0 0 220 150">
      <circle cx="70" cy="75" r="45" fill="transparent" stroke="rgba(255,255,255,0.05)" strokeWidth="16" />
      {data.map((item, idx) => {
        if (total === 0) return null;
        const percent = item.value / total;
        const strokeDash = 2 * Math.PI * 45;
        const strokeDasharray = `${percent * strokeDash} ${strokeDash}`;
        const strokeDashoffset = -accumulatedPercent * strokeDash;
        accumulatedPercent += percent;
        
        return (
          <circle
            key={idx}
            cx="70"
            cy="75"
            r="45"
            fill="transparent"
            stroke={item.color}
            strokeWidth="16"
            strokeDasharray={strokeDasharray}
            strokeDashoffset={strokeDashoffset}
            transform="rotate(-90 70 75)"
          />
        );
      })}
      {/* Legend */}
      <g transform="translate(130, 25)" style={{ fontSize: '10px', fill: '#9CA3AF', fontFamily: 'sans-serif' }}>
        {data.map((item, idx) => (
          <g key={idx} transform={`translate(0, ${idx * 22})`}>
            <rect width="10" height="10" rx="2" fill={item.color} />
            <text x="16" y="9" fontWeight="600">{item.label}</text>
            <text x="16" y="20" fill="var(--text-muted)" fontSize="8.5px">{item.value} candidates</text>
          </g>
        ))}
      </g>
    </svg>
  );
};

// SVG Bar Chart Component
const BarChart = ({ data }) => {
  const maxVal = Math.max(...data.map(d => d.value), 1);
  return (
    <svg width="320" height="150" viewBox="0 0 320 150">
      {data.map((item, idx) => {
        const height = (item.value / maxVal) * 90;
        const x = 30 + idx * 60;
        const y = 120 - height;
        return (
          <g key={idx}>
            <text x={x + 15} y={y - 6} fill="#F3F4F6" fontSize="9" textAnchor="middle" fontWeight="bold">{item.value}</text>
            <rect x={x} y={y} width="30" height={height} fill="url(#barGradient)" rx="4" />
            <text x={x + 15} y={136} fill="#9CA3AF" fontSize="8.5px" textAnchor="middle" fontWeight="600">{item.label}</text>
          </g>
        );
      })}
      <defs>
        <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#8B5CF6" />
          <stop offset="100%" stopColor="#6366F1" />
        </linearGradient>
      </defs>
    </svg>
  );
};

export default function App() {
  // Session Authentication
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [username, setUsername] = useState(localStorage.getItem('username'));
  const [authView, setAuthView] = useState('login'); // 'login' | 'register'
  const [authUsername, setAuthUsername] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [authSuccess, setAuthSuccess] = useState('');

  // Workspace View
  const [view, setView] = useState('landing'); // 'landing' | 'auth' | 'workspace'
  const [activeTab, setActiveTab] = useState('shortlist'); // 'shortlist' | 'compare' | 'analytics'
  const [rightPanelTab, setRightPanelTab] = useState('details'); // 'details' | 'ai_assistant'
  
  // Roles Management
  const [roles, setRoles] = useState(['default']);
  const [activeRoleId, setActiveRoleId] = useState('default');
  const [showCreateRoleModal, setShowCreateRoleModal] = useState(false);
  const [newRoleInput, setNewRoleInput] = useState('');

  // Candidate Shortlist Data
  const [candidates, setCandidates] = useState([]);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [jd, setJd] = useState('');
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [rankingInProgress, setRankingInProgress] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Status & Custom Imports
  const [status, setStatus] = useState({ has_custom_jd: false, has_custom_candidates: false, candidates_count: 0 });
  const [editJd, setEditJd] = useState(false);
  const [jdInput, setJdInput] = useState('');
  const [uploadingCandidates, setUploadingCandidates] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState('');
  const [showSyncWarning, setShowSyncWarning] = useState(false);
  const [tourStep, setTourStep] = useState(null);

  // Side-by-Side Comparison
  const [selectedForComparison, setSelectedForComparison] = useState([]);

  // AI Assistant Chat state
  const [chatMessages, setChatMessages] = useState([
    { sender: 'bot', text: 'Hello! I am your AI Recruiter Assistant. I can help analyze, search, compare, or write candidate emails. Feel free to ask me anything!' }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [geminiApiKey, setGeminiApiKey] = useState(localStorage.getItem('geminiApiKey') || '');
  const [parsedJd, setParsedJd] = useState(null);
  const [showParsedJd, setShowParsedJd] = useState(true);

  // Custom API fetch wrapper with Auth Token and auto logout
  const apiFetch = async (url, options = {}) => {
    const headers = { ...options.headers };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401) {
      handleClientLogout();
      throw new Error("Unauthorized");
    }
    return res;
  };

  const handleClientLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    setToken(null);
    setUsername(null);
    setView('landing');
  };

  const enterWorkspace = () => {
    if (!token) {
      setAuthView('login');
      setView('auth');
    } else {
      setView('workspace');
      if (!localStorage.getItem('seenOnboardingTour')) {
        setTourStep(1);
      }
    }
  };

  // Auth Operations
  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');
    setAuthSuccess('');

    const endpoint = authView === 'login' ? '/api/auth/login' : '/api/auth/register';
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: authUsername, password: authPassword })
      });
      const data = await res.json();
      if (!res.ok) {
        setAuthError(data.detail || 'Authentication failed.');
        return;
      }

      if (authView === 'register') {
        setAuthSuccess('Registration successful! Please login.');
        setAuthView('login');
        setAuthPassword('');
      } else {
        localStorage.setItem('token', data.token);
        localStorage.setItem('username', data.username);
        setToken(data.token);
        setUsername(data.username);
        setAuthUsername('');
        setAuthPassword('');
        setView('workspace');
        if (!localStorage.getItem('seenOnboardingTour')) {
          setTourStep(1);
        }
      }
    } catch (e) {
      setAuthError('Connection error.');
    }
  };

  const handleLogout = async () => {
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' });
    } catch (e) {}
    handleClientLogout();
  };

  // Load backend details
  useEffect(() => {
    if (token) {
      fetchRoles();
      fetchJd();
      fetchCandidates();
      fetchStatus();
      fetchParsedJd();
    }
  }, [token, activeRoleId]);

  const fetchRoles = async () => {
    try {
      const res = await apiFetch('/api/roles');
      const data = await res.json();
      if (data.roles) {
        setRoles(data.roles);
      }
    } catch (e) {}
  };

  const createRole = async () => {
    const name = newRoleInput.trim().toLowerCase().replace(/\s+/g, '_');
    if (!name) return;
    try {
      const res = await apiFetch('/api/roles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role_id: name })
      });
      const data = await res.json();
      if (res.ok) {
        await fetchRoles();
        setActiveRoleId(name);
        setNewRoleInput('');
        setShowCreateRoleModal(false);
      } else {
        alert(data.detail || 'Failed to create role.');
      }
    } catch (e) {}
  };

  const deleteRole = async (roleName) => {
    if (roleName === 'default') return;
    if (!window.confirm(`Are you sure you want to delete the role workspace: "${roleName}"?`)) return;
    try {
      const res = await apiFetch(`/api/roles/${roleName}`, { method: 'DELETE' });
      if (res.ok) {
        setActiveRoleId('default');
        await fetchRoles();
      }
    } catch (e) {}
  };

  const fetchStatus = async () => {
    try {
      const res = await apiFetch(`/api/status?role_id=${activeRoleId}`);
      const data = await res.json();
      setStatus(data);
    } catch (e) {}
  };

  const fetchJd = async () => {
    try {
      const res = await apiFetch(`/api/job-description?role_id=${activeRoleId}`);
      const data = await res.json();
      const content = data.content || '';
      setJd(content);
      setJdInput(content);
    } catch (e) {}
  };

  const fetchParsedJd = async () => {
    try {
      const res = await apiFetch(`/api/job-description/parsed?role_id=${activeRoleId}`);
      const data = await res.json();
      setParsedJd(data);
    } catch (e) {}
  };

  const fetchCandidates = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const res = await apiFetch(`/api/candidates?role_id=${activeRoleId}`);
      const data = await res.json();
      if (data.status === 'success') {
        setCandidates(data.candidates || []);
        if (data.candidates && data.candidates.length > 0) {
          setSelectedCandidate(data.candidates[0]);
        } else {
          setSelectedCandidate(null);
        }
      } else {
        setErrorMsg(data.message || 'Failed to load candidates.');
      }
    } catch (e) {
      setErrorMsg('Failed to connect to backend server.');
    } finally {
      setLoading(false);
    }
  };

  const saveJd = async () => {
    try {
      const res = await apiFetch('/api/job-description', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: jdInput, role_id: activeRoleId })
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        setJd(jdInput);
        setEditJd(false);
        setShowSyncWarning(true);
        await fetchStatus();
        await fetchParsedJd();
      } else {
        alert(data.detail || 'Failed to save job description.');
      }
    } catch (e) {
      alert('Error communicating with server.');
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    if (!file.name.endsWith('.jsonl') && !file.name.endsWith('.csv')) {
      setUploadError('Only .jsonl or .csv files are allowed.');
      setUploadSuccess('');
      return;
    }

    setUploadingCandidates(true);
    setUploadError('');
    setUploadSuccess('');
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await apiFetch(`/api/upload-candidates?role_id=${activeRoleId}`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        setUploadSuccess('Candidates pool uploaded successfully!');
        setShowSyncWarning(true);
        await fetchStatus();
        setCandidates([]);
        setSelectedCandidate(null);
        setErrorMsg('New pool loaded. Please run Recalculate Ranks.');
      } else {
        setUploadError(data.detail || 'Failed to upload candidates.');
      }
    } catch (e) {
      setUploadError('Network error uploading candidates.');
    } finally {
      setUploadingCandidates(false);
      event.target.value = null;
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Are you sure you want to restore the default dataset and job description? All custom edits for this role will be deleted.')) {
      return;
    }
    try {
      const res = await apiFetch(`/api/reset?role_id=${activeRoleId}`, { method: 'POST' });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        setShowSyncWarning(false);
        setUploadSuccess('');
        setUploadError('');
        setEditJd(false);
        await fetchJd();
        await fetchStatus();
        await fetchCandidates();
        await fetchParsedJd();
      } else {
        alert(data.detail || 'Failed to reset workspace.');
      }
    } catch (e) {
      alert('Network error resetting workspace.');
    }
  };

  const triggerRanking = async () => {
    setRankingInProgress(true);
    setErrorMsg('');
    try {
      const headers = {};
      if (geminiApiKey) {
        headers['X-Gemini-Key'] = geminiApiKey;
      }
      const res = await apiFetch(`/api/rank?role_id=${activeRoleId}`, { 
        method: 'POST',
        headers
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        setShowSyncWarning(false);
        await fetchCandidates();
        await fetchStatus();
        await fetchParsedJd();
      } else {
        setErrorMsg(data.detail || data.message || 'Ranking failed.');
      }
    } catch (e) {
      setErrorMsg('Error communicating with ranker server.');
    } finally {
      setRankingInProgress(false);
    }
  };

  const handleExportCsv = async () => {
    try {
      const res = await apiFetch(`/api/download-csv?role_id=${activeRoleId}`);
      if (!res.ok) {
        if (res.status === 404) {
          alert("No submission CSV generated yet. Please click 'Recalculate Ranks' first.");
          return;
        }
        alert("Failed to export CSV.");
        return;
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `team_submission_${activeRoleId}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      alert("Error exporting CSV.");
    }
  };

  // AI Chat integration
  const handleSendChatMessage = async (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userMsg = chatInput.trim();
    setChatMessages(prev => [...prev, { sender: 'user', text: userMsg }]);
    setChatInput('');
    setChatLoading(true);

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (geminiApiKey) {
        headers['X-Gemini-Key'] = geminiApiKey;
      }
      
      const res = await apiFetch('/api/ai/chat', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: userMsg,
          role_id: activeRoleId,
          gemini_api_key: geminiApiKey || null
        })
      });
      const data = await res.json();
      if (res.ok) {
        setChatMessages(prev => [...prev, { sender: 'bot', text: data.response, engine: data.engine }]);
      } else {
        setChatMessages(prev => [...prev, { sender: 'bot', text: 'Sorry, I failed to generate an answer. Check your connection.' }]);
      }
    } catch (err) {
      setChatMessages(prev => [...prev, { sender: 'bot', text: 'Error contacting AI backend.' }]);
    } finally {
      setChatLoading(false);
    }
  };

  const saveGeminiKey = (key) => {
    setGeminiApiKey(key);
    localStorage.setItem('geminiApiKey', key);
  };

  // Compare candidates matrix toggles
  const toggleComparisonSelection = (id) => {
    if (selectedForComparison.includes(id)) {
      setSelectedForComparison(prev => prev.filter(item => item !== id));
    } else {
      if (selectedForComparison.length >= 4) {
        alert("You can compare up to 4 candidates at a time.");
        return;
      }
      setSelectedForComparison(prev => [...prev, id]);
    }
  };

  const filteredCandidates = candidates.filter(c => {
    const query = search.toLowerCase();
    const name = (c.details?.profile?.anonymized_name || '').toLowerCase();
    const title = (c.details?.profile?.current_title || '').toLowerCase();
    const skills = (c.details?.skills || []).map(s => (s.name || '').toLowerCase()).join(' ');
    const reason = (c.reasoning || '').toLowerCase();
    
    return name.includes(query) || title.includes(query) || skills.includes(query) || reason.includes(query);
  });

  // Calculate statistics for Analytics Dashboard
  const getAnalyticsData = () => {
    const yoeCounts = { '< 3': 0, '3-5': 0, '5-9': 0, '9-12': 0, '> 12': 0 };
    const noticeCounts = { 'Immediate (<=30d)': 0, 'Standard (31-60d)': 0, 'Extended (61-90d)': 0, 'Long (>90d)': 0 };
    const pedigreeCounts = { 'Product': 0, 'Consulting': 0, 'Neutral': 0 };

    candidates.forEach(cand => {
      const profile = cand.details?.profile || {};
      const signals = cand.details?.redrob_signals || {};
      
      // YoE distribution
      const yoe = profile.years_of_experience || 0;
      if (yoe < 3) yoeCounts['< 3']++;
      else if (yoe < 5) yoeCounts['3-5']++;
      else if (yoe <= 9) yoeCounts['5-9']++;
      else if (yoe <= 12) yoeCounts['9-12']++;
      else yoeCounts['> 12']++;

      // Notice period distribution
      const notice = signals.notice_period_days || 0;
      if (notice <= 30) noticeCounts['Immediate (<=30d)']++;
      else if (notice <= 60) noticeCounts['Standard (31-60d)']++;
      else if (notice <= 90) noticeCounts['Extended (61-90d)']++;
      else noticeCounts['Long (>90d)']++;

      // Pedigree distribution
      const history = cand.details?.career_history || [];
      const consulting_firms = ["tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini", "tech mahindra", "mphasis", "mindtree", "hcl", "genpact"];
      const product_firms = ["hooli", "pied piper", "wayne enterprises", "stark industries", "initech", "globex inc", "tyrell corp", "cyberdyne systems", "acme corp", "razorpay", "cred", "flipkart", "zomato", "swiggy", "paytm", "meesho", "nykaa", "freshworks", "ola", "phonepe"];
      
      const companies = history.map(j => (j.company || '').toLowerCase());
      const all_consulting = companies.length > 0 && companies.every(comp => consulting_firms.some(cf => comp.includes(cf)));
      const has_product = companies.some(comp => product_firms.some(pf => comp.includes(pf)));
      
      if (has_product) pedigreeCounts['Product']++;
      else if (all_consulting) pedigreeCounts['Consulting']++;
      else pedigreeCounts['Neutral']++;
    });

    const yoeData = Object.keys(yoeCounts).map(k => ({ label: k, value: yoeCounts[k] }));
    const noticeData = [
      { label: 'Immediate (<=30d)', value: noticeCounts['Immediate (<=30d)'], color: '#10B981' },
      { label: 'Standard (31-60d)', value: noticeCounts['Standard (31-60d)'], color: '#6366F1' },
      { label: 'Extended (61-90d)', value: noticeCounts['Extended (61-90d)'], color: '#F59E0B' },
      { label: 'Long (>90d)', value: noticeCounts['Long (>90d)'], color: '#F43F5E' },
    ];
    const pedigreeData = [
      { label: 'Product Tech', value: pedigreeCounts['Product'], color: '#06B6D4' },
      { label: 'Consulting-Only', value: pedigreeCounts['Consulting'], color: '#F43F5E' },
      { label: 'Neutral Cohort', value: pedigreeCounts['Neutral'], color: '#8B5CF6' }
    ];

    return { yoeData, noticeData, pedigreeData };
  };

  const { yoeData, noticeData, pedigreeData } = getAnalyticsData();

  const getScoreColorClass = (score) => {
    if (score >= 0.8) return 'score-high';
    if (score >= 0.6) return 'score-medium';
    if (score >= 0.4) return 'score-low';
    return 'score-poor';
  };

  // Rendering of Landing Page
  if (view === 'landing') {
    return (
      <div className="landing-container">
        <header className="landing-nav">
          <div className="brand-section">
            <div className="brand-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <div>
              <h1 className="brand-title">REDROB</h1>
              <p className="brand-subtitle">Talent Intelligence</p>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {token ? (
              <>
                <span style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>Welcome, <strong>{username}</strong></span>
                <button className="nav-right-btn" onClick={() => setView('workspace')}>Go to Console</button>
                <button className="nav-right-btn" style={{ background: 'transparent' }} onClick={handleLogout}>Logout</button>
              </>
            ) : (
              <>
                <button className="nav-right-btn" style={{ background: 'transparent' }} onClick={() => { setAuthView('login'); setView('auth'); }}>Sign In</button>
                <button className="nav-right-btn" onClick={() => { setAuthView('register'); setView('auth'); }}>Register</button>
              </>
            )}
          </div>
        </header>

        <main className="landing-hero">
          <div className="hero-tag">
            <span className="hero-tag-dot"></span>
            Next-Gen Recruiter Console
          </div>
          <h2 className="hero-main-title">
            Bypass Resumes. <br />
            <span className="hero-gradient-text">Identify Real Shippers.</span>
          </h2>
          <p className="hero-desc">
            An AI-powered candidate ranking engine. Eliminate keyword stuffing, screen for timeline honeypots, isolate product pedigree, and integrate active behavioral signals automatically.
          </p>

          <div className="cta-container">
            <button className="landing-cta-btn" onClick={enterWorkspace}>
              <span>Enter Recruiter Console</span>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </button>
            <span className="cta-sub-label">Access candidate index, customize JDs, and trigger real-time rank runs</span>
          </div>

          <section className="landing-stats">
            <div className="stat-item">
              <span className="stat-num">100k+</span>
              <span className="stat-label">Indexed Profiles</span>
            </div>
            <div className="stat-item">
              <span className="stat-num">0%</span>
              <span className="stat-label">Honeypots Tolerated</span>
            </div>
            <div className="stat-item">
              <span className="stat-num">0.1s</span>
              <span className="stat-label">Precompute Query</span>
            </div>
            <div className="stat-item">
              <span className="stat-num">99.8%</span>
              <span className="stat-label">Precision Rate</span>
            </div>
          </section>
        </main>

        <section className="landing-pillars">
          <div className="section-label-centered">
            <h3>4 Core Refinement Modules</h3>
            <p>High-signal screening rules working concurrently to filter out noisy applications</p>
          </div>

          <div className="pillars-grid">
            <div className="pillar-card">
              <div className="pillar-header">
                <div className="pillar-icon-box">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <h4 className="pillar-title">Honeypot Disqualification</h4>
              </div>
              <p className="pillar-desc">
                Profiles with impossible timeline anomalies (e.g. starting senior software engineer roles years before college graduation) are automatically detected and pushed to the bottom.
              </p>
            </div>

            <div className="pillar-card">
              <div className="pillar-header">
                <div className="pillar-icon-box">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                <h4 className="pillar-title">Anti-Keyword Stuffers</h4>
              </div>
              <p className="pillar-desc">
                Filters applicants who stuff hot keywords (e.g. PyTorch, LLMs, RAG) but have only held unrelated non-technical positions (sales, marketing, HR) with no genuine engineering tenure.
              </p>
            </div>

            <div className="pillar-card">
              <div className="pillar-header">
                <div className="pillar-icon-box">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  </svg>
                </div>
                <h4 className="pillar-title">Pedigree Isolation</h4>
              </div>
              <p className="pillar-desc">
                Identifies product engineering experience versus consulting-only profiles. Emphasizes product-based development and startup shippers while strictly deprioritizing IT consulting services.
              </p>
            </div>

            <div className="pillar-card">
              <div className="pillar-header">
                <div className="pillar-icon-box">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <h4 className="pillar-title">Active Behavioral Signals</h4>
              </div>
              <p className="pillar-desc">
                Integrates recruiter response rates, interview completions, open-to-work flags, last-active dates, and GitHub contribution scores to ensure you target active, responsive candidates.
              </p>
            </div>
          </div>
        </section>

        <footer className="landing-footer">
          <span>&copy; 2026 Redrob Inc. All rights reserved.</span>
          <a href="#" className="footer-link" onClick={(e) => { e.preventDefault(); enterWorkspace(); }}>Launch Console</a>
        </footer>
      </div>
    );
  }

  // Rendering of Login/Register View
  if (view === 'auth') {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '20px' }}>
            <div className="brand-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
          </div>
          <h2 className="auth-title">{authView === 'login' ? 'Welcome Back' : 'Create Account'}</h2>
          <p className="auth-subtitle">
            {authView === 'login' ? 'Sign in to access your talent console' : 'Register to get started with Redrob'}
          </p>

          {authError && <div style={{ color: 'var(--accent-rose)', background: 'rgba(244,63,94,0.1)', padding: '10px', borderRadius: '8px', fontSize: '12px', marginBottom: '16px', fontWeight: 600 }}>{authError}</div>}
          {authSuccess && <div style={{ color: 'var(--accent-emerald)', background: 'rgba(16,185,129,0.1)', padding: '10px', borderRadius: '8px', fontSize: '12px', marginBottom: '16px', fontWeight: 600 }}>{authSuccess}</div>}

          <form className="auth-form" onSubmit={handleAuthSubmit}>
            <div className="form-group">
              <label className="form-label">Username</label>
              <input 
                type="text" 
                className="auth-input" 
                value={authUsername}
                onChange={e => setAuthUsername(e.target.value)}
                placeholder="Enter username" 
                required 
              />
            </div>
            <div className="form-group">
              <label className="form-label">Password</label>
              <input 
                type="password" 
                className="auth-input" 
                value={authPassword}
                onChange={e => setAuthPassword(e.target.value)}
                placeholder="Enter password" 
                required 
              />
            </div>
            <button type="submit" className="auth-submit-btn">
              {authView === 'login' ? 'Sign In' : 'Register Account'}
            </button>
          </form>

          <p className="auth-switch-prompt">
            {authView === 'login' ? "Don't have an account?" : "Already have an account?"}
            <span className="auth-link" onClick={() => { setAuthView(authView === 'login' ? 'register' : 'login'); setAuthError(''); setAuthSuccess(''); }}>
              {authView === 'login' ? 'Register Now' : 'Sign In'}
            </span>
          </p>

          <p className="auth-switch-prompt" style={{ marginTop: '16px' }}>
            <span className="auth-link" style={{ color: 'var(--text-muted)' }} onClick={() => setView('landing')}>
              &larr; Back to Landing Page
            </span>
          </p>
        </div>
      </div>
    );
  }

  // Rendering of Main Recruiter Console Workspace View
  return (
    <div className="app-layout">
      {/* Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <div>
            <h1 className="brand-title">REDROB</h1>
            <p className="brand-subtitle">Talent Intelligence</p>
          </div>
          
          {/* Multi-Role Selector */}
          <div className="role-selector-container" style={{ marginLeft: '24px' }}>
            <select 
              className="role-select" 
              value={activeRoleId} 
              onChange={e => setActiveRoleId(e.target.value)}
            >
              {roles.map(r => (
                <option key={r} value={r}>Role: {r.toUpperCase().replace(/_/g, ' ')}</option>
              ))}
            </select>
            <div className="role-actions">
              <button className="role-btn" title="Create New Role" onClick={() => setShowCreateRoleModal(true)}>
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ width: 14, height: 14 }}>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
                </svg>
              </button>
              {activeRoleId !== 'default' && (
                <button className="role-btn delete" title="Delete Active Role" onClick={() => deleteRole(activeRoleId)}>
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ width: 14, height: 14 }}>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              )}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button className="btn-back-home" onClick={() => setView('landing')}>
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            Home Landing
          </button>

          <button className="btn-tour-help" title="Replay Onboarding Tour" onClick={() => setTourStep(1)}>
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </button>

          <button 
            onClick={triggerRanking} 
            disabled={rankingInProgress}
            className={`recalculate-btn ${rankingInProgress ? 'btn-loading' : ''}`}
          >
            {rankingInProgress ? (
              <>
                <svg className="spinner" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Analyzing Pool...
              </>
            ) : (
              <>
                <svg className="btn-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 8H18.2" />
                </svg>
                Recalculate Ranks
              </>
            )}
          </button>

          {candidates.length > 0 && (
            <button 
              onClick={handleExportCsv}
              className="recalculate-btn"
              style={{ background: 'var(--accent-emerald)', borderColor: 'var(--accent-emerald)' }}
              title="Export ranked list to Excel-compatible CSV file"
            >
              <svg className="btn-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Export to Excel
            </button>
          )}

          {/* User profile details */}
          <div className="user-avatar-btn" onClick={handleLogout} title="Logout of console">
            <span className="user-initials">{username ? username.substring(0,2).toUpperCase() : 'UR'}</span>
            <span>Sign Out</span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="main-content">
        
        {/* Left Panel: Job Description */}
        <aside className={`sidebar-jd ${tourStep === 1 ? 'tour-highlight' : ''}`}>
          <div className="sidebar-header">
            <span className="sidebar-label">Active Target Role</span>
            <h2 className="role-title" style={{ fontSize: '14px', textTransform: 'capitalize' }}>
              {activeRoleId.replace(/_/g, ' ')}
            </h2>
            <p className="team-label">Founding Recruiter Space</p>
          </div>
          
          <div className="sidebar-scrollable">
            {/* Custom Input Configuration Card */}
            <div className="focus-card glass dataset-card">
              <h3 className="card-title">Role Pool Config</h3>
              
              <div className="status-indicator">
                <div className="status-row">
                  <span>JD Parameters:</span>
                  <span className={`status-badge-inline ${status.has_custom_jd ? 'status-custom' : 'status-default'}`}>
                    {status.has_custom_jd ? 'Custom (Active)' : 'Default'}
                  </span>
                </div>
                <div className="status-row">
                  <span>Talent Pool:</span>
                  <span className={`status-badge-inline ${status.has_custom_candidates ? 'status-custom' : 'status-default'}`}>
                    {status.has_custom_candidates ? `Custom (${status.candidates_count} items)` : 'Default (100k)'}
                  </span>
                </div>
              </div>
              
              <div className="upload-container">
                <label className="upload-btn-label">
                  <svg className="upload-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  <span>{uploadingCandidates ? 'Uploading...' : 'Upload CSV or JSONL'}</span>
                  <input 
                    type="file" 
                    accept=".jsonl,.csv" 
                    onChange={handleFileUpload} 
                    disabled={uploadingCandidates} 
                    style={{ display: 'none' }}
                  />
                </label>
                
                {uploadError && <div className="upload-feedback error">{uploadError}</div>}
                {uploadSuccess && <div className="upload-feedback success">{uploadSuccess}</div>}
              </div>

              {/* CSV Columns Guide */}
              <details className="csv-guide-details" style={{ marginTop: 10 }}>
                <summary className="csv-guide-summary" style={{ fontSize: '10px', color: 'var(--accent-indigo)', cursor: 'pointer', fontWeight: 600 }}>
                  View Expected CSV Headers
                </summary>
                <div className="csv-guide-content" style={{ fontSize: '9.5px', color: 'var(--text-secondary)', marginTop: 4, lineHeight: '1.4', background: 'rgba(0,0,0,0.15)', padding: 6, borderRadius: 4 }}>
                  <strong>Supported CSV Headers:</strong>
                  <ul style={{ paddingLeft: 12, marginTop: 2 }}>
                    <li><code>name</code></li>
                    <li><code>title</code></li>
                    <li><code>company</code></li>
                    <li><code>yoe</code> (Years of Experience)</li>
                    <li><code>skills</code> (comma-separated list)</li>
                    <li><code>location</code></li>
                    <li><code>notice_period_days</code></li>
                  </ul>
                </div>
              </details>

              {(status.has_custom_jd || status.has_custom_candidates) && (
                <button className="reset-btn-sidebar" onClick={handleReset} style={{ marginTop: 12 }}>
                  Restore Default Dataset
                </button>
              )}
            </div>

            <div className="focus-card glass">
              <h3 className="card-title">Key Core Pillars</h3>
              <ul className="focus-list">
                <li><span className="bullet" />Stage 1: Safety Check & Pedigree</li>
                <li><span className="bullet" />Stage 2: Dense Semantic Score</li>
                <li><span className="bullet" />Stage 3: YoE & Growth Boosters</li>
                <li><span className="bullet" />Stage 4: Active Platform Signals</li>
              </ul>
            </div>
            
            <div className="jd-section">
              <div className="jd-section-header">
                <h3 className="section-title">Job Description Content</h3>
                {!editJd ? (
                  <button className="edit-jd-btn" onClick={() => setEditJd(true)}>
                    <svg viewBox="0 0 20 20" fill="currentColor" className="edit-icon" style={{width: 12, height: 12}}>
                      <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
                    </svg>
                    Edit
                  </button>
                ) : (
                  <div className="jd-edit-actions">
                    <button className="jd-action-btn save" onClick={saveJd}>Save</button>
                    <button className="jd-action-btn cancel" onClick={() => { setEditJd(false); setJdInput(jd); }}>Cancel</button>
                  </div>
                )}
              </div>
              
              {editJd ? (
                <textarea 
                  className="jd-editor-textarea"
                  value={jdInput}
                  onChange={e => setJdInput(e.target.value)}
                  placeholder="Paste or type a new Job Description here..."
                />
              ) : (
                <div className="jd-viewer">
                  {jd || 'Loading job description...'}
                </div>
              )}
            </div>

            {parsedJd && !editJd && (
              <div className="parsed-jd-panel glass">
                <div className="parsed-jd-header" onClick={() => setShowParsedJd(!showParsedJd)}>
                  <h4 className="parsed-jd-title-text">
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{width: 14, height: 14, marginRight: 6}}>
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Parsed JD Insights
                  </h4>
                  <button className="toggle-parsed-btn">
                    {showParsedJd ? 'Hide' : 'Show'}
                  </button>
                </div>
                {showParsedJd && (
                  <div className="parsed-jd-content">
                    <div className="parsed-field">
                      <span className="parsed-label">Extracted Role:</span>
                      <span className="parsed-value text-glow">{parsedJd.title}</span>
                    </div>
                    <div className="parsed-field">
                      <span className="parsed-label">Experience Band:</span>
                      <span className="parsed-value">{parsedJd.experience_min} - {parsedJd.experience_max} Years</span>
                    </div>
                    <div className="parsed-field">
                      <span className="parsed-label">Core Tech Stack:</span>
                      <div className="parsed-chips">
                        {(parsedJd.tech_skills || []).map((skill, idx) => (
                          <span key={idx} className="parsed-chip tech">{skill}</span>
                        ))}
                      </div>
                    </div>
                    <div className="parsed-field">
                      <span className="parsed-label">AI & Search Concepts:</span>
                      <div className="parsed-chips">
                        {(parsedJd.ir_skills || []).map((skill, idx) => (
                          <span key={idx} className="parsed-chip ir">{skill}</span>
                        ))}
                      </div>
                    </div>
                    <div className="parsed-field">
                      <span className="parsed-label">Behavioral Signals:</span>
                      <div className="parsed-chips">
                        {(parsedJd.behavioral_priorities || []).map((priority, idx) => (
                          <span key={idx} className="parsed-chip behavioral">{priority}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </aside>

        {/* Center Panel Tabs */}
        <section className={`shortlist-panel ${tourStep === 2 ? 'tour-highlight' : ''}`} style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="tabs-container">
            <button 
              className={`tab-btn ${activeTab === 'shortlist' ? 'active' : ''}`}
              onClick={() => setActiveTab('shortlist')}
            >
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
              </svg>
              Ranked Shortlist
            </button>
            <button 
              className={`tab-btn ${activeTab === 'compare' ? 'active' : ''}`}
              onClick={() => setActiveTab('compare')}
            >
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10a2 2 0 01-2 2h-2a2 2 0 01-2-2zm9 0v-8a2 2 0 00-2-2h-2a2 2 0 00-2 2v8a2 2 0 002 2h2a2 2 0 002-2z" />
              </svg>
              Comparison Matrix
            </button>
            <button 
              className={`tab-btn ${activeTab === 'analytics' ? 'active' : ''}`}
              onClick={() => setActiveTab('analytics')}
            >
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
              </svg>
              Pool Analytics
            </button>
          </div>

          {/* TAB 1: Ranked Shortlist */}
          {activeTab === 'shortlist' && (
            <>
              {showSyncWarning && (
                <div className="sync-warning-banner">
                  <svg className="warning-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <div>
                    <span className="warning-title">Ranks Out of Sync</span>
                    <p className="warning-desc">Source data has changed. Please click <strong>Recalculate Ranks</strong> to update rankings.</p>
                  </div>
                </div>
              )}
              
              <div className="toolbar">
                <div className="search-bar">
                  <svg className="search-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <input 
                    type="text" 
                    placeholder="Search by name, skill, title..." 
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                  />
                </div>
                <div className="count-label">
                  Shortlisted: <span className="highlight">{filteredCandidates.length}</span> / {candidates.length}
                </div>
              </div>

              <div className="candidates-list">
                {loading ? (
                  <div className="centered-state">
                    <svg className="spinner-large" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <p>Loading candidate index...</p>
                  </div>
                ) : errorMsg ? (
                  <div className="centered-state error-state">
                    <div className="error-icon-box">
                      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                    </div>
                    <h3>No Candidate Index Found</h3>
                    <p>{errorMsg}</p>
                    <button onClick={triggerRanking} className="action-btn">
                      Generate Index Now
                    </button>
                  </div>
                ) : candidates.length === 0 ? (
                  <div className="centered-state empty-state" style={{ flexDirection: 'column', gap: '16px', maxWidth: '420px', margin: '40px auto', textAlign: 'center', display: 'flex', alignItems: 'center' }}>
                    <div className="error-icon-box" style={{ background: 'rgba(99, 102, 241, 0.1)', color: 'var(--accent-indigo)' }}>
                      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ width: 32, height: 32 }}>
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                      </svg>
                    </div>
                    <h3 style={{ color: '#fff', fontSize: '15px', fontWeight: 800 }}>Workspace Setup Pending</h3>
                    <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                      No candidate shortlist has been calculated for this role space yet. To get started:
                    </p>
                    <ul style={{ textAlign: 'left', fontSize: '11.5px', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '6px', paddingLeft: '16px' }}>
                      <li>1. Type and save a target <strong>Job Description</strong> on the left panel.</li>
                      <li>2. Upload a candidates pool CSV or JSONL file using the config card.</li>
                      <li>3. Click the <strong>Recalculate Ranks</strong> button in the header.</li>
                    </ul>
                    <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', marginTop: '8px' }}>
                      Or, click <strong>Restore Default Dataset</strong> on the left to instantly load the Demo Sandbox data to try it out!
                    </div>
                  </div>
                ) : filteredCandidates.length === 0 ? (
                  <div className="centered-state empty-state">
                    No candidates match your search filter.
                  </div>
                ) : (
                  <div className="list-container">
                    {filteredCandidates.map((cand) => {
                      const isSelected = selectedCandidate?.candidate_id === cand.candidate_id;
                      const profile = cand.details?.profile || {};
                      const isCompared = selectedForComparison.includes(cand.candidate_id);
                      return (
                        <div 
                          key={cand.candidate_id}
                          onClick={() => setSelectedCandidate(cand)}
                          className={`candidate-item glow-on-hover ${isSelected ? 'selected' : ''}`}
                        >
                          <div className="item-left" onClick={(e) => e.stopPropagation()}>
                            <input 
                              type="checkbox" 
                              title="Select to compare"
                              checked={isCompared}
                              onChange={() => toggleComparisonSelection(cand.candidate_id)}
                              style={{ marginRight: 4, cursor: 'pointer' }}
                            />
                            <div className={`rank-badge ${cand.rank <= 3 ? 'top-rank' : ''}`}>
                              #{cand.rank}
                            </div>
                            <div className="item-meta" onClick={() => setSelectedCandidate(cand)} style={{ cursor: 'pointer' }}>
                              <div className="name-row">
                                <span className="candidate-name">{profile.anonymized_name || cand.candidate_id}</span>
                                {cand.details?.redrob_signals?.open_to_work_flag && (
                                  <span className="open-badge">OPEN</span>
                                )}
                              </div>
                              <p className="headline-text">{profile.headline || 'Software Engineer'}</p>
                            </div>
                          </div>

                          <div className="item-right">
                            <div className="demographics">
                              <span>{profile.years_of_experience || 0} YoE</span>
                              <span className="divider">•</span>
                              <span className="loc-text">{profile.location || 'India'}</span>
                            </div>
                            
                            {cand.honeypot_reason && (
                              <span className="fraud-badge-list" title={cand.honeypot_reason}>⚠️ FRAUD</span>
                            )}
                            
                            <div className="confidence-badge-container">
                              <div className={`score-badge confidence ${getScoreColorClass(cand.score)}`}>
                                {cand.confidence_score ? `${Math.round(cand.confidence_score)}%` : `${Math.round(cand.score * 100)}%`}
                              </div>
                              <span className="score-badge-label">confidence</span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          )}

          {/* TAB 2: Comparison Matrix */}
          {activeTab === 'compare' && (
            <div className="comparison-view">
              <div className="comparison-selector-panel">
                <span className="chart-title">Select Candidates to Compare (Max 4)</span>
                <div className="selector-grid">
                  {candidates.slice(0, 15).map(c => {
                    const isChecked = selectedForComparison.includes(c.candidate_id);
                    const name = c.details?.profile?.anonymized_name || c.candidate_id;
                    return (
                      <label key={c.candidate_id} className={`cand-checkbox-label ${isChecked ? 'checked' : ''}`}>
                        <input 
                          type="checkbox" 
                          checked={isChecked}
                          onChange={() => toggleComparisonSelection(c.candidate_id)}
                          style={{ display: 'none' }}
                        />
                        <span>#{c.rank} - {name.substring(0, 16)}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              {selectedForComparison.length === 0 ? (
                <div className="centered-state glass" style={{ padding: '40px', borderRadius: '16px' }}>
                  Please check the boxes above or in the list view to select candidates for comparison.
                </div>
              ) : (
                <div className="comparison-table-wrapper">
                  <table className="comparison-table">
                    <thead>
                      <tr>
                        <th className="parameter-col">Parameter</th>
                        {selectedForComparison.map(cid => {
                          const cand = candidates.find(c => c.candidate_id === cid);
                          return (
                            <th key={cid}>
                              #{cand?.rank} - {cand?.details?.profile?.anonymized_name || cid}
                            </th>
                          );
                        })}
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td className="parameter-col">Ranking Score</td>
                        {selectedForComparison.map(cid => {
                          const cand = candidates.find(c => c.candidate_id === cid);
                          return (
                            <td key={cid} style={{ fontWeight: 'bold' }}>
                              <span className={`score-badge ${getScoreColorClass(cand?.score || 0)}`} style={{ padding: '3px 8px', borderRadius: '6px' }}>
                                {cand?.score.toFixed(4)}
                              </span>
                            </td>
                          );
                        })}
                      </tr>
                      <tr>
                        <td className="parameter-col">Current Role</td>
                        {selectedForComparison.map(cid => {
                          const cand = candidates.find(c => c.candidate_id === cid);
                          return <td key={cid}>{cand?.details?.profile?.current_title || 'N/A'}</td>;
                        })}
                      </tr>
                      <tr>
                        <td className="parameter-col">Current Company</td>
                        {selectedForComparison.map(cid => {
                          const cand = candidates.find(c => c.candidate_id === cid);
                          return <td key={cid}>{cand?.details?.profile?.current_company || 'N/A'}</td>;
                        })}
                      </tr>
                      <tr>
                        <td className="parameter-col">Years of Exp (YoE)</td>
                        {selectedForComparison.map(cid => {
                          const cand = candidates.find(c => c.candidate_id === cid);
                          const yoe = cand?.details?.profile?.years_of_experience || 0;
                          return (
                            <td key={cid} className={yoe >= 5 && yoe <= 9 ? 'diff-high' : ''}>
                              {yoe} Years
                            </td>
                          );
                        })}
                      </tr>
                      <tr>
                        <td className="parameter-col">Notice Period</td>
                        {selectedForComparison.map(cid => {
                          const cand = candidates.find(c => c.candidate_id === cid);
                          const notice = cand?.details?.redrob_signals?.notice_period_days || 0;
                          return (
                            <td key={cid} className={notice <= 30 ? 'diff-high' : notice > 60 ? 'diff-low' : ''}>
                              {notice} Days
                            </td>
                          );
                        })}
                      </tr>
                      <tr>
                        <td className="parameter-col">Recruiter Response</td>
                        {selectedForComparison.map(cid => {
                          const cand = candidates.find(c => c.candidate_id === cid);
                          const rate = Math.round((cand?.details?.redrob_signals?.recruiter_response_rate || 0) * 100);
                          return <td key={cid}>{rate}%</td>;
                        })}
                      </tr>
                      <tr>
                        <td className="parameter-col">GitHub Score</td>
                        {selectedForComparison.map(cid => {
                          const cand = candidates.find(c => c.candidate_id === cid);
                          const git = cand?.details?.redrob_signals?.github_activity_score;
                          return (
                            <td key={cid} className={git > 40 ? 'diff-high' : ''}>
                              {git !== -1 ? git : 'N/A'}
                            </td>
                          );
                        })}
                      </tr>
                      <tr>
                        <td className="parameter-col">Location</td>
                        {selectedForComparison.map(cid => {
                          const cand = candidates.find(c => c.candidate_id === cid);
                          return <td key={cid}>{cand?.details?.profile?.location || 'N/A'}</td>;
                        })}
                      </tr>
                      <tr>
                        <td className="parameter-col">Top Skills</td>
                        {selectedForComparison.map(cid => {
                          const cand = candidates.find(c => c.candidate_id === cid);
                          const skills = (cand?.details?.skills || []).slice(0, 3).map(s => s.name).join(', ');
                          return <td key={cid}>{skills || 'N/A'}</td>;
                        })}
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: Pool Analytics */}
          {activeTab === 'analytics' && (
            <div className="analytics-view">
              <div className="analytics-grid">
                
                {/* Chart 1: Experience Bands */}
                <div className="analytics-card">
                  <span className="chart-title">Years of Experience (YoE) Distribution</span>
                  <div className="chart-container">
                    <BarChart data={yoeData} />
                  </div>
                </div>

                {/* Chart 2: Notice Period */}
                <div className="analytics-card">
                  <span className="chart-title">Notice Period Breakdown</span>
                  <div className="chart-container">
                    <DonutChart data={noticeData} />
                  </div>
                </div>

                {/* Chart 3: Pedigree Breakdown */}
                <div className="analytics-card">
                  <span className="chart-title">Pedigree Cohorts Breakdown</span>
                  <div className="chart-container">
                    <DonutChart data={pedigreeData} />
                  </div>
                </div>

                {/* Stat Box Summary */}
                <div className="analytics-card" style={{ justifyContent: 'center', gap: '12px' }}>
                  <span className="chart-title" style={{ color: 'var(--accent-indigo)' }}>Core Insights Summary</span>
                  <p style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                    - **Peak sweet spot**: Candidates with 5-9 years of experience are boosted, helping you find developers in their highest shipping capacity.
                    <br />
                    - **Pedigree Calibrator**: Product company engineering tenures are highlighted with a 15% score multiplier, whereas consulting histories are downweighted.
                    <br />
                    - **Immediate Joiners**: {noticeData[0].value} candidates have under 30 days notice period, representing immediate pipeline conversions.
                  </p>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Right Panel: Tabbed Details & AI Assistant */}
        <section className={`details-panel ${tourStep === 3 ? 'tour-highlight' : ''}`}>
          
          <div className="right-drawer-header">
            <button 
              className={`drawer-tab ${rightPanelTab === 'details' ? 'active' : ''}`}
              onClick={() => setRightPanelTab('details')}
            >
              Candidate Details
            </button>
            <button 
              className={`drawer-tab ${rightPanelTab === 'ai_assistant' ? 'active' : ''}`}
              onClick={() => setRightPanelTab('ai_assistant')}
            >
              AI Recruiter Assistant
            </button>
          </div>

          {rightPanelTab === 'details' ? (
            selectedCandidate ? (
              <div className="details-content">
                {selectedCandidate.honeypot_reason && (
                  <div className="fraud-alert-banner">
                    <div className="alert-banner-header">
                      <span className="alert-icon">⚠️</span>
                      <h4 className="alert-banner-title">Dynamic Safety Alert: Potential Fraud / Anomaly</h4>
                    </div>
                    <p className="alert-body">{selectedCandidate.honeypot_reason}</p>
                  </div>
                )}

                <div className="details-header">
                  <div className="header-meta">
                    <h2 className="detail-name">{selectedCandidate.details?.profile?.anonymized_name || selectedCandidate.candidate_id}</h2>
                    <p className="detail-title">{selectedCandidate.details?.profile?.current_title || 'Software Engineer'}</p>
                    <p className="detail-company">at {selectedCandidate.details?.profile?.current_company || 'Product Company'}</p>
                  </div>
                  <div className={`detail-score-box ${getScoreColorClass(selectedCandidate.score)}`}>
                    <span className="score-label">Match Confidence</span>
                    <span className="score-val">
                      {selectedCandidate.confidence_score ? `${Math.round(selectedCandidate.confidence_score)}%` : `${Math.round(selectedCandidate.score * 100)}%`}
                    </span>
                  </div>
                </div>

                <div className="justification-box">
                  <h3 className="box-header">
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    AI Match Justification
                  </h3>
                  <p className="box-content">
                    {selectedCandidate.reasoning}
                  </p>
                </div>

                {selectedCandidate.why_cards && (
                  <div className="details-section why-ranked-section">
                    <h3 className="section-heading">Why Ranked Here?</h3>
                    <div className="pros-cons-grid">
                      <div className="why-column pros-column">
                        <h4 className="column-title strengths">Strengths / Positive Signals</h4>
                        <ul className="why-list pro-list">
                          {(selectedCandidate.why_cards.pros || []).map((pro, index) => (
                            <li key={index} className="why-item pro-item">
                              <span className="icon">✓</span>
                              <span className="text">{pro}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div className="why-column cons-column">
                        <h4 className="column-title risks">Risk Factors / Gaps</h4>
                        <ul className="why-list con-list">
                          {(selectedCandidate.why_cards.cons || []).map((con, index) => (
                            <li key={index} className="why-item con-item">
                              <span className="icon">⚠</span>
                              <span className="text">{con}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                )}

                {selectedCandidate.skill_gap && (
                  <div className="details-section skill-gap-section">
                    <h3 className="section-heading">Skill Gap Analysis</h3>
                    <div className="gap-grid">
                      <div className="gap-half">
                        <span className="gap-title matching">Matching Stack Skills</span>
                        <div className="gap-chips">
                          {(selectedCandidate.skill_gap.matching || []).map((skill, index) => (
                            <span key={index} className="gap-chip matching-chip">{skill}</span>
                          ))}
                          {(!selectedCandidate.skill_gap.matching || selectedCandidate.skill_gap.matching.length === 0) && (
                            <span className="empty-italic">No matching core stack skills found</span>
                          )}
                        </div>
                      </div>
                      <div className="gap-half">
                        <span className="gap-title missing">Missing Required Skills</span>
                        <div className="gap-chips">
                          {(selectedCandidate.skill_gap.missing || []).map((skill, index) => (
                            <span key={index} className="gap-chip missing-chip">{skill}</span>
                          ))}
                          {(!selectedCandidate.skill_gap.missing || selectedCandidate.skill_gap.missing.length === 0) && (
                            <span className="gap-chip all-matched-chip">✓ All Core Skills Matched</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {selectedCandidate.requirements_breakdown && (
                  <div className="details-section breakdown-section">
                    <h3 className="section-heading">Match Requirements Breakdown</h3>
                    <div className="breakdown-grid">
                      {selectedCandidate.requirements_breakdown.map((req, index) => (
                        <div key={index} className="breakdown-item">
                          <div className="breakdown-info">
                            <span className="breakdown-label">{req.label}</span>
                            <span className="breakdown-val">{req.score}%</span>
                          </div>
                          <div className="progress-bar-bg">
                            <div 
                              className={`progress-bar-fill ${
                                req.score >= 80 ? 'emerald-fill' : (req.score >= 50 ? 'amber-fill' : 'rose-fill')
                              }`}
                              style={{ width: `${req.score}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="details-section">
                  <h3 className="section-heading">Verified Skills</h3>
                  <div className="skills-cloud">
                    {(selectedCandidate.details?.skills || []).map((skill, i) => (
                      <span key={i} className="skill-tag">
                        {skill.name}
                      </span>
                    ))}
                    {(!selectedCandidate.details?.skills || selectedCandidate.details.skills.length === 0) && (
                      <span className="empty-italic">No verified skills listed</span>
                    )}
                  </div>
                </div>

                <div className="details-section">
                  <h3 className="section-heading">Behavioral Availability Signals</h3>
                  <div className="signals-grid">
                    
                    <div className="signal-card glass">
                      <span className="signal-label">Recruiter Response</span>
                      <div className="signal-value-row">
                        <span className="value-num">{Math.round((selectedCandidate.details?.redrob_signals?.recruiter_response_rate || 0) * 100)}%</span>
                        <span className="value-unit">rate</span>
                      </div>
                      <div className="progress-bar-bg">
                        <div 
                          className="progress-bar-fill indigo-fill" 
                          style={{ width: `${(selectedCandidate.details?.redrob_signals?.recruiter_response_rate || 0) * 100}%` }}
                        />
                      </div>
                    </div>

                    <div className="signal-card glass">
                      <span className="signal-label">Interview Completion</span>
                      <div className="signal-value-row">
                        <span className="value-num">{Math.round((selectedCandidate.details?.redrob_signals?.interview_completion_rate || 0) * 100)}%</span>
                        <span className="value-unit">rate</span>
                      </div>
                      <div className="progress-bar-bg">
                        <div 
                          className="progress-bar-fill violet-fill" 
                          style={{ width: `${(selectedCandidate.details?.redrob_signals?.interview_completion_rate || 0) * 100}%` }}
                        />
                      </div>
                    </div>

                    <div className="signal-card glass">
                      <span className="signal-label">GitHub Activity</span>
                      <div className="value-num value-offset">
                        {selectedCandidate.details?.redrob_signals?.github_activity_score !== -1 
                          ? selectedCandidate.details?.redrob_signals?.github_activity_score 
                          : 'No Account'}
                      </div>
                      <span className="sub-unit">Open-source score</span>
                    </div>

                    <div className="signal-card glass">
                      <span className="signal-label">Notice Period</span>
                      <div className="value-num value-offset">
                        {selectedCandidate.details?.redrob_signals?.notice_period_days || 0} Days
                      </div>
                      <span className="sub-unit">Lead availability time</span>
                    </div>
                  </div>
                </div>

                <div className="details-section">
                  <h3 className="section-heading">Career History</h3>
                  <div className="timeline-container">
                    {(selectedCandidate.details?.career_history || []).map((job, idx) => (
                      <div key={idx} className="timeline-item">
                        <div className="timeline-node" />
                        <div className="timeline-body">
                          <h4 className="job-title">{job.title}</h4>
                          <div className="job-meta">
                            <span className="company-text">{job.company}</span>
                            <span className="job-divider">•</span>
                            <span>{job.duration_months} mos</span>
                          </div>
                          {job.description && (
                            <p className="job-desc">
                              {job.description}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                    {(!selectedCandidate.details?.career_history || selectedCandidate.details.career_history.length === 0) && (
                      <p className="empty-italic pl-4">No career history listed</p>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="centered-state details-placeholder">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
                <p>Select a candidate to view timeline and platform signals</p>
              </div>
            )
          ) : (
            // TAB: AI Recruiter Assistant
            <div className="ai-assistant-container">
              <div className="ai-key-config">
                <span className="form-label" style={{ fontSize: '9px', whiteSpace: 'nowrap' }}>Gemini Key:</span>
                <input 
                  type="password" 
                  className="ai-key-input" 
                  value={geminiApiKey}
                  onChange={e => saveGeminiKey(e.target.value)}
                  placeholder="Enter Gemini API Key (optional)" 
                />
              </div>

              <div className="chat-messages">
                {chatMessages.map((msg, i) => (
                  <div key={i} className={`chat-bubble ${msg.sender}`}>
                    {renderMarkdown(msg.text)}
                    {msg.engine && (
                      <span className={`ai-engine-badge ${msg.engine.includes('gemini') ? 'gemini' : 'local'}`}>
                        Engine: {msg.engine.toUpperCase().replace(/_/g, ' ')}
                      </span>
                    )}
                  </div>
                ))}
                {chatLoading && (
                  <div className="chat-bubble bot" style={{ display: 'flex', alignItems: 'center' }}>
                    <div className="typing-indicator">
                      <div className="typing-dot" />
                      <div className="typing-dot" />
                      <div className="typing-dot" />
                    </div>
                  </div>
                )}
              </div>

              <form className="chat-input-area" onSubmit={handleSendChatMessage}>
                <input 
                  type="text" 
                  className="chat-input"
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  disabled={chatLoading}
                  placeholder="Ask about candidates or draft emails..."
                />
                <button type="submit" className="chat-send-btn" disabled={chatLoading || !chatInput.trim()}>
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ width: 16, height: 16 }}>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </button>
              </form>
            </div>
          )}
        </section>

      </div>

      {/* CREATE ROLE MODAL */}
      {showCreateRoleModal && (
        <div className="modal-overlay">
          <div className="modal-card">
            <h3 className="modal-header">Create Target Role Space</h3>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              Create a new isolated role space with its own target job description and custom talent pool.
            </p>
            <div className="form-group">
              <label className="form-label">Role Name</label>
              <input 
                type="text" 
                className="auth-input"
                value={newRoleInput}
                onChange={e => setNewRoleInput(e.target.value)}
                placeholder="e.g. Founding ML Lead"
                required
              />
            </div>
            <div className="modal-actions">
              <button className="modal-btn secondary" onClick={() => { setShowCreateRoleModal(false); setNewRoleInput(''); }}>
                Cancel
              </button>
              <button className="modal-btn primary" onClick={createRole} disabled={!newRoleInput.trim()}>
                Create Space
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Onboarding Tour Overlay & Tooltip */}
      {tourStep !== null && (
        <>
          <div className="tour-overlay" onClick={() => {
            localStorage.setItem('seenOnboardingTour', 'true');
            setTourStep(null);
          }} />
          <div 
            className="tour-tooltip"
            style={
              tourStep === 1 
                ? { left: '340px', top: '120px' }
                : tourStep === 2
                ? { left: '50%', top: '120px', transform: 'translateX(-50%)' }
                : { right: '470px', top: '120px' }
            }
          >
            <span className="tour-step-badge">Step {tourStep} of 3</span>
            <h4 className="tour-title">
              {tourStep === 1 && "Data Pool & Target Role"}
              {tourStep === 2 && "Ranked Candidate Shortlist"}
              {tourStep === 3 && "Profile Deep Dive & AI Match"}
            </h4>
            <p className="tour-desc">
              {tourStep === 1 && "Configure your target Job Description guidelines, upload custom candidate CSV/JSONL profiles, check pool sync states, and refer to expected headers."}
              {tourStep === 2 && "View matched candidates ranked by our 4-Stage hybrid model. Filter lists in real-time, search by keywords, and execute fresh recalculation runs."}
              {tourStep === 3 && "Examine detailed verified skills, career history timelines, and platform availability signals. Read unique, non-templated AI justifications for fit."}
            </p>
            <div className="tour-footer">
              <button className="tour-btn-skip" onClick={() => {
                localStorage.setItem('seenOnboardingTour', 'true');
                setTourStep(null);
              }}>
                Skip Tour
              </button>
              <div className="tour-actions-right">
                {tourStep > 1 && (
                  <button className="tour-btn-prev" onClick={() => setTourStep(tourStep - 1)}>
                    Back
                  </button>
                )}
                <button 
                  className="tour-btn-next" 
                  onClick={() => {
                    if (tourStep < 3) {
                      setTourStep(tourStep + 1);
                    } else {
                      localStorage.setItem('seenOnboardingTour', 'true');
                      setTourStep(null);
                    }
                  }}
                >
                  {tourStep === 3 ? "Get Started" : "Next Step"}
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
