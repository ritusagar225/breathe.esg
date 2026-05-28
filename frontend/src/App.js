import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

const API = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const SCOPE_COLORS = { SCOPE_1: '#ef4444', SCOPE_2: '#3b82f6', SCOPE_3: '#8b5cf6' };
const STATUS_COLORS = { PENDING: '#f59e0b', FLAGGED: '#ef4444', APPROVED: '#10b981', REJECTED: '#6b7280' };
const SOURCE_LABELS = {
  SAP_FUEL: 'SAP Fuel', SAP_PROCUREMENT: 'SAP Procurement',
  UTILITY_ELECTRICITY: 'Electricity', TRAVEL_FLIGHT: 'Travel',
  TRAVEL_HOTEL: 'Travel Hotel', TRAVEL_GROUND: 'Travel Ground',
};

function StatCard({ label, value, color, sub }) {
  return (
    <div className="stat-card">
      <div className="stat-value" style={{ color }}>{value}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

function Badge({ text, color }) {
  return <span className="badge" style={{ background: color + '22', color, border: `1px solid ${color}44` }}>{text}</span>;
}

export default function App() {
  const [tab, setTab] = useState('dashboard');
  const [stats, setStats] = useState(null);
  const [records, setRecords] = useState([]);
  const [batches, setBatches] = useState([]);
  const [sources, setSources] = useState([]);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterSource, setFilterSource] = useState('');
  const [reviewModal, setReviewModal] = useState(null);
  const [reviewReason, setReviewReason] = useState('');
  const [uploadSource, setUploadSource] = useState('');
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadMsg, setUploadMsg] = useState('');
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);

  const fetchStats = useCallback(async () => {
    const r = await fetch(`${API}/api/stats/`);
    setStats(await r.json());
  }, []);

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    let url = `${API}/api/records/?`;
    if (filterStatus) url += `status=${filterStatus}&`;
    if (filterSource) url += `source_type=${filterSource}&`;
    const r = await fetch(url);
    setRecords(await r.json());
    setLoading(false);
  }, [filterStatus, filterSource]);

  const fetchBatches = useCallback(async () => {
    const r = await fetch(`${API}/api/batches/`);
    setBatches(await r.json());
  }, []);

  const fetchSources = useCallback(async () => {
    const r = await fetch(`${API}/api/sources/`);
    setSources(await r.json());
  }, []);

  useEffect(() => { fetchStats(); fetchSources(); }, [fetchStats, fetchSources]);
  useEffect(() => { if (tab === 'records') fetchRecords(); }, [tab, fetchRecords]);
  useEffect(() => { if (tab === 'batches') fetchBatches(); }, [tab, fetchBatches]);

  const submitReview = async (newStatus) => {
    if ((newStatus === 'APPROVED' || newStatus === 'REJECTED') && !reviewReason.trim()) {
      alert('Please provide a reason.');
      return;
    }
    await fetch(`${API}/api/records/${reviewModal.id}/review/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ review_status: newStatus, reason: reviewReason, analyst: 'analyst@demo.com' }),
    });
    setReviewModal(null);
    setReviewReason('');
    fetchRecords();
    fetchStats();
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!uploadSource || !uploadFile) { setUploadMsg('Please select a source and file.'); return; }
    setUploading(true);
    setUploadMsg('');
    const fd = new FormData();
    fd.append('source_id', uploadSource);
    fd.append('file', uploadFile);
    try {
      const r = await fetch(`${API}/api/ingest/`, { method: 'POST', body: fd });
      const d = await r.json();
      if (r.ok) {
        setUploadMsg(`✓ Ingested ${d.rows_ingested} rows (${d.rows_failed} failed)`);
        fetchStats();
        fetchBatches();
      } else {
        setUploadMsg(`✗ ${d.error}`);
      }
    } catch (err) {
      setUploadMsg(`✗ Network error`);
    }
    setUploading(false);
  };

  const fmt = (n) => n == null ? '—' : parseFloat(n).toLocaleString('en-GB', { maximumFractionDigits: 1 });
  const fmtCO2 = (n) => n == null ? '—' : (parseFloat(n) / 1000).toFixed(2) + ' tCO₂e';

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">🌱</span>
            <span className="logo-text">Breathe ESG</span>
            <span className="logo-sub">Ingestion Platform</span>
          </div>
          <nav className="nav">
            {['dashboard', 'records', 'batches', 'upload'].map(t => (
              <button key={t} className={`nav-btn ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </nav>
          <div className="header-tenant">Demo Corp</div>
        </div>
      </header>

      <main className="main">
        {tab === 'dashboard' && stats && (
          <div className="dashboard">
            <h2 className="page-title">Overview</h2>
            <div className="stats-grid">
              <StatCard label="Total Records" value={stats.total} color="#1e293b" />
              <StatCard label="Pending Review" value={stats.pending} color="#f59e0b" />
              <StatCard label="Flagged" value={stats.flagged} color="#ef4444" sub="Require attention" />
              <StatCard label="Approved" value={stats.approved} color="#10b981" />
              <StatCard label="Rejected" value={stats.rejected} color="#6b7280" />
            </div>

            <h2 className="page-title" style={{ marginTop: 40 }}>CO₂e by Scope</h2>
            <div className="scope-grid">
              {Object.entries(stats.co2e_by_scope).map(([scope, val]) => (
                <div key={scope} className="scope-card" style={{ borderTop: `4px solid ${SCOPE_COLORS[scope]}` }}>
                  <div className="scope-name" style={{ color: SCOPE_COLORS[scope] }}>{scope.replace('_', ' ')}</div>
                  <div className="scope-value">{(val / 1000).toFixed(2)}</div>
                  <div className="scope-unit">tCO₂e</div>
                </div>
              ))}
            </div>

            <div className="info-box">
              <strong>Demo credentials:</strong> analyst@demo.com / demo1234 &nbsp;|&nbsp;
              This prototype uses hardcoded auth — see DECISIONS.md for why.
            </div>
          </div>
        )}

        {tab === 'records' && (
          <div>
            <div className="toolbar">
              <h2 className="page-title">Activity Records</h2>
              <div className="filters">
                <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className="select">
                  <option value="">All statuses</option>
                  <option value="PENDING">Pending</option>
                  <option value="FLAGGED">Flagged</option>
                  <option value="APPROVED">Approved</option>
                  <option value="REJECTED">Rejected</option>
                </select>
                <select value={filterSource} onChange={e => setFilterSource(e.target.value)} className="select">
                  <option value="">All sources</option>
                  <option value="SAP_FUEL">SAP Fuel</option>
                  <option value="UTILITY_ELECTRICITY">Electricity</option>
                  <option value="TRAVEL_FLIGHT">Travel</option>
                </select>
                <button className="btn-primary" onClick={fetchRecords}>Apply</button>
              </div>
            </div>

            {loading ? <div className="loading">Loading…</div> : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Date</th><th>Source</th><th>Scope</th><th>Description</th>
                      <th>Location</th><th>Quantity</th><th>CO₂e</th><th>Status</th><th>Flags</th><th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map(r => (
                      <tr key={r.id} className={r.review_status === 'FLAGGED' ? 'row-flagged' : ''}>
                        <td className="cell-date">{r.activity_date}</td>
                        <td><Badge text={SOURCE_LABELS[r.source_type] || r.source_type} color="#475569" /></td>
                        <td><Badge text={r.scope} color={SCOPE_COLORS[r.scope]} /></td>
                        <td className="cell-desc">{r.description}</td>
                        <td className="cell-loc">{r.location}</td>
                        <td className="cell-num">{fmt(r.quantity)} {r.unit}</td>
                        <td className="cell-num">{fmtCO2(r.quantity_co2e_kg)}</td>
                        <td><Badge text={r.review_status} color={STATUS_COLORS[r.review_status]} /></td>
                        <td>
                          {Object.keys(r.flags || {}).map(f => (
                            <span key={f} className="flag-chip" title={f}>⚠ {f.replace(/_/g, ' ')}</span>
                          ))}
                        </td>
                        <td>
                          {r.review_status !== 'APPROVED' && r.review_status !== 'REJECTED' && (
                            <button className="btn-review" onClick={() => { setReviewModal(r); setReviewReason(''); }}>
                              Review
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {records.length === 0 && <div className="empty">No records found.</div>}
              </div>
            )}
          </div>
        )}

        {tab === 'batches' && (
          <div>
            <h2 className="page-title">Ingestion History</h2>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>File</th><th>Source</th><th>Ingested</th><th>Rows OK</th><th>Errors</th><th>Status</th></tr>
                </thead>
                <tbody>
                  {batches.map(b => (
                    <tr key={b.id}>
                      <td>{b.file_name}</td>
                      <td><Badge text={SOURCE_LABELS[b.source_type] || b.source_type} color="#475569" /></td>
                      <td>{new Date(b.ingested_at).toLocaleString('en-GB')}</td>
                      <td className="cell-num">{b.row_count}</td>
                      <td className="cell-num" style={{ color: b.error_count > 0 ? '#ef4444' : 'inherit' }}>{b.error_count}</td>
                      <td><Badge text={b.status} color={b.status === 'COMPLETE' ? '#10b981' : '#ef4444'} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {batches.length === 0 && <div className="empty">No batches yet.</div>}
            </div>
          </div>
        )}

        {tab === 'upload' && (
          <div className="upload-page">
            <h2 className="page-title">Upload Data</h2>
            <div className="upload-card">
              <p className="upload-hint">
                Upload a CSV file for any configured data source. The system will parse, normalize,
                and flag records for analyst review.
              </p>
              <div className="form-group">
                <label className="form-label">Data Source</label>
                <select className="select" value={uploadSource} onChange={e => setUploadSource(e.target.value)}>
                  <option value="">Select source…</option>
                  {sources.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">CSV File</label>
                <input type="file" accept=".csv" className="file-input"
                  onChange={e => setUploadFile(e.target.files[0])} />
              </div>
              <button className="btn-primary" onClick={handleUpload} disabled={uploading}>
                {uploading ? 'Uploading…' : 'Upload & Ingest'}
              </button>
              {uploadMsg && (
                <div className={`upload-msg ${uploadMsg.startsWith('✓') ? 'success' : 'error'}`}>
                  {uploadMsg}
                </div>
              )}
              <div className="sample-files">
                <strong>Sample files for testing:</strong>
                <ul>
                  <li><code>sap_fuel_mb51.csv</code> → SAP MB51 — Fuel Consumption</li>
                  <li><code>utility_electricity.csv</code> → Utility Portal — Electricity</li>
                  <li><code>concur_travel.csv</code> → Concur — Business Travel</li>
                </ul>
              </div>
            </div>
          </div>
        )}
      </main>

      {reviewModal && (
        <div className="modal-overlay" onClick={() => setReviewModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3 className="modal-title">Review Record</h3>
            <div className="modal-row"><span>Description</span><strong>{reviewModal.description}</strong></div>
            <div className="modal-row"><span>Date</span><strong>{reviewModal.activity_date}</strong></div>
            <div className="modal-row"><span>Quantity</span><strong>{fmt(reviewModal.quantity)} {reviewModal.unit}</strong></div>
            <div className="modal-row"><span>CO₂e</span><strong>{fmtCO2(reviewModal.quantity_co2e_kg)}</strong></div>
            <div className="modal-row"><span>Location</span><strong>{reviewModal.location}</strong></div>
            {Object.keys(reviewModal.flags || {}).length > 0 && (
              <div className="modal-flags">
                <span>⚠ Flags: </span>
                {Object.keys(reviewModal.flags).map(f => <span key={f} className="flag-chip">{f.replace(/_/g, ' ')}</span>)}
              </div>
            )}
            <div className="form-group">
              <label className="form-label">Reason <span className="required">(required for approve/reject)</span></label>
              <textarea className="textarea" rows={3} value={reviewReason}
                onChange={e => setReviewReason(e.target.value)}
                placeholder="e.g. Verified against plant manager report. Values match." />
            </div>
            <div className="modal-actions">
              <button className="btn-approve" onClick={() => submitReview('APPROVED')}>✓ Approve</button>
              <button className="btn-reject" onClick={() => submitReview('REJECTED')}>✗ Reject</button>
              <button className="btn-flag" onClick={() => submitReview('FLAGGED')}>⚠ Flag</button>
              <button className="btn-cancel" onClick={() => setReviewModal(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
