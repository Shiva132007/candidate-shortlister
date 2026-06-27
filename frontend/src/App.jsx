import React, { useState, useEffect } from 'react';

export default function App() {
  const [candidates, setCandidates] = useState([]);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [jd, setJd] = useState('');
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [rankingInProgress, setRankingInProgress] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const [status, setStatus] = useState({ has_custom_jd: false, has_custom_candidates: false, candidates_count: 0 });
  const [editJd, setEditJd] = useState(false);
  const [jdInput, setJdInput] = useState('');
  const [uploadingCandidates, setUploadingCandidates] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState('');
  const [showSyncWarning, setShowSyncWarning] = useState(false);

  useEffect(() => {
    fetchJd();
    fetchCandidates();
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/status');
      const data = await res.json();
      setStatus(data);
    } catch (e) {
      console.error("Error fetching status", e);
    }
  };

  const fetchJd = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/job-description');
      const data = await res.json();
      const content = data.content || '';
      setJd(content);
      setJdInput(content);
    } catch (e) {
      console.error("Error fetching JD", e);
    }
  };

  const fetchCandidates = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const res = await fetch('http://127.0.0.1:8000/api/candidates');
      const data = await res.json();
      if (data.status === 'success') {
        setCandidates(data.candidates || []);
        if (data.candidates && data.candidates.length > 0) {
          setSelectedCandidate(data.candidates[0]);
        }
      } else {
        setErrorMsg(data.message || 'Failed to load candidates.');
      }
    } catch (e) {
      setErrorMsg('Failed to connect to backend server.');
      console.error("Error fetching candidates", e);
    } finally {
      setLoading(false);
    }
  };

  const saveJd = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/job-description', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: jdInput })
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        setJd(jdInput);
        setEditJd(false);
        setShowSyncWarning(true);
        await fetchStatus();
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
      const res = await fetch('http://127.0.0.1:8000/api/upload-candidates', {
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
    if (!window.confirm('Are you sure you want to restore the default dataset and job description? All custom edits will be deleted.')) {
      return;
    }
    try {
      const res = await fetch('http://127.0.0.1:8000/api/reset', { method: 'POST' });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        setShowSyncWarning(false);
        setUploadSuccess('');
        setUploadError('');
        setEditJd(false);
        await fetchJd();
        await fetchStatus();
        await fetchCandidates();
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
      const res = await fetch('http://127.0.0.1:8000/api/rank', { method: 'POST' });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        setShowSyncWarning(false);
        await fetchCandidates();
        await fetchStatus();
      } else {
        setErrorMsg(data.detail || data.message || 'Ranking failed.');
      }
    } catch (e) {
      setErrorMsg('Error communicating with ranker server.');
    } finally {
      setRankingInProgress(false);
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

  const getScoreColorClass = (score) => {
    if (score >= 0.8) return 'score-high';
    if (score >= 0.6) return 'score-medium';
    if (score >= 0.4) return 'score-low';
    return 'score-poor';
  };

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
        </div>

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
      </header>

      {/* Main Content Area */}
      <div className="main-content">
        
        {/* Left Panel: Job Description */}
        <aside className="sidebar-jd">
          <div className="sidebar-header">
            <span className="sidebar-label">Target Role</span>
            <h2 className="role-title">Senior AI Engineer</h2>
            <p className="team-label">Founding Team</p>
          </div>
          
          <div className="sidebar-scrollable">
            {/* Custom Input Configuration Card */}
            <div className="focus-card glass dataset-card">
              <h3 className="card-title">Data Pool Config</h3>
              
              <div className="status-indicator">
                <div className="status-row">
                  <span>Job Description:</span>
                  <span className={`status-badge-inline ${status.has_custom_jd ? 'status-custom' : 'status-default'}`}>
                    {status.has_custom_jd ? 'Custom (Active)' : 'Default'}
                  </span>
                </div>
                <div className="status-row">
                  <span>Candidates Pool:</span>
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
                    <li><code>name</code> (or <code>anonymized_name</code>)</li>
                    <li><code>title</code> (or <code>current_title</code>)</li>
                    <li><code>company</code> (or <code>current_company</code>)</li>
                    <li><code>yoe</code> (or <code>years_of_experience</code>)</li>
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
              <h3 className="card-title">Key Focus Areas</h3>
              <ul className="focus-list">
                <li><span className="bullet" />Applied ML & Evaluation</li>
                <li><span className="bullet" />Embeddings-based Retrieval</li>
                <li><span className="bullet" />Search/Retrieval Systems</li>
                <li><span className="bullet" />Evaluations (NDCG, MAP, MRR)</li>
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
          </div>
        </aside>

        {/* Center Panel: Candidate Shortlist */}
        <section className="shortlist-panel">
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
            ) : filteredCandidates.length === 0 ? (
              <div className="centered-state empty-state">
                No candidates match your search filter.
              </div>
            ) : (
              <div className="list-container">
                {filteredCandidates.map((cand) => {
                  const isSelected = selectedCandidate?.candidate_id === cand.candidate_id;
                  const profile = cand.details?.profile || {};
                  return (
                    <div 
                      key={cand.candidate_id}
                      onClick={() => setSelectedCandidate(cand)}
                      className={`candidate-item glow-on-hover ${isSelected ? 'selected' : ''}`}
                    >
                      <div className="item-left">
                        <div className={`rank-badge ${cand.rank <= 3 ? 'top-rank' : ''}`}>
                          #{cand.rank}
                        </div>
                        <div className="item-meta">
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
                        <div className={`score-badge ${getScoreColorClass(cand.score)}`}>
                          {cand.score.toFixed(4)}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        {/* Right Panel: Candidate Profile Deep Dive */}
        <section className="details-panel">
          {selectedCandidate ? (
            <div className="details-content">
              
              {/* Profile Header Card */}
              <div className="details-header">
                <div className="header-meta">
                  <h2 className="detail-name">{selectedCandidate.details?.profile?.anonymized_name || selectedCandidate.candidate_id}</h2>
                  <p className="detail-title">{selectedCandidate.details?.profile?.current_title || 'Software Engineer'}</p>
                  <p className="detail-company">at {selectedCandidate.details?.profile?.current_company || 'Product Company'}</p>
                </div>
                <div className={`detail-score-box ${getScoreColorClass(selectedCandidate.score)}`}>
                  <span className="score-label">Score</span>
                  <span className="score-val">{selectedCandidate.score.toFixed(4)}</span>
                </div>
              </div>

              {/* Match Justification Box */}
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

              {/* Skills cloud */}
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

              {/* Behavioral Availability Signals */}
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

              {/* Career History timeline */}
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
          )}
        </section>

      </div>
    </div>
  );
}
