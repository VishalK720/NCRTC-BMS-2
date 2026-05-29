import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import client from '../api/client.js';
import { getUser } from '../api/auth.js';
import Modal from '../components/Modal.jsx';

const STATUSES = ['open', 'acknowledged', 'in_progress', 'resolved', 'closed'];
const SEVERITIES = ['P1', 'P2', 'P3'];
const NEXT_STATUS = {
  open: 'acknowledged',
  acknowledged: 'in_progress',
  in_progress: 'resolved',
  resolved: 'closed',
};

function SeverityBadge({ severity }) {
  const cls = severity === 'P1' ? 'badge-p1' : severity === 'P2' ? 'badge-p2' : 'badge-p3';
  return <span className={`badge ${cls}`}>{severity}</span>;
}

export default function Incidents() {
  const user = getUser();
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [showRaise, setShowRaise] = useState(false);
  const [statusNote, setStatusNote] = useState('');
  const [toStatus, setToStatus] = useState('');
  const [assignUserId, setAssignUserId] = useState('');

  const [raiseForm, setRaiseForm] = useState({
    type: 'breakdown',
    severity: 'P2',
    description: '',
    depot_id: user?.depot_id || 1,
    vehicle_id: '',
  });

  const { data: incidents = [], isLoading } = useQuery({
    queryKey: ['incidents', statusFilter, severityFilter],
    queryFn: async () => {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (severityFilter) params.severity = severityFilter;
      const { data } = await client.get('/incidents', { params });
      return data;
    },
  });

  const { data: vehicles = [] } = useQuery({
    queryKey: ['incidents-vehicles', user?.depot_id],
    queryFn: async () => {
      const params = user?.depot_id ? { depot_id: user.depot_id } : {};
      const { data } = await client.get('/avls/vehicles', { params });
      return data;
    },
  });

  const depotId = user?.depot_id || 1;
  const { data: roster } = useQuery({
    queryKey: ['incidents-roster-users', depotId],
    queryFn: async () => {
      const monday = new Date();
      const day = monday.getDay();
      const diff = day === 0 ? -6 : 1 - day;
      monday.setDate(monday.getDate() + diff);
      const week_start = monday.toISOString().slice(0, 10);
      const { data } = await client.get('/scheduling/roster', {
        params: { depot_id: depotId, week_start },
      });
      return data;
    },
  });

  const assigneeOptions = useMemo(() => {
    return (roster?.rows || []).map((r) => ({
      id: r.driver_id,
      name: r.driver_name,
    }));
  }, [roster]);

  const vehicleRegMap = useMemo(() => {
    const m = {};
    vehicles.forEach((v) => {
      m[v.id] = v.reg_no;
    });
    return m;
  }, [vehicles]);

  const { data: detail } = useQuery({
    queryKey: ['incident', selectedId],
    queryFn: async () => {
      const { data } = await client.get(`/incidents/${selectedId}`);
      return data;
    },
    enabled: Boolean(selectedId),
  });

  const createMutation = useMutation({
    mutationFn: (body) => client.post('/incidents', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['incidents'] });
      setShowRaise(false);
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, to_status, note }) =>
      client.put(`/incidents/${id}/status`, { to_status, note: note || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['incidents'] });
      qc.invalidateQueries({ queryKey: ['incident', selectedId] });
      setStatusNote('');
    },
  });

  const assignMutation = useMutation({
    mutationFn: ({ id, assigned_to }) => client.put(`/incidents/${id}/assign`, { assigned_to }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['incidents'] });
      qc.invalidateQueries({ queryKey: ['incident', selectedId] });
    },
  });

  const canManage = ['admin', 'depot_manager', 'control_operator'].includes(user?.role);
  const nextForDetail = detail ? NEXT_STATUS[detail.status] : null;

  return (
    <div>
      <h1>Incidents</h1>
      <div className="form-row" style={{ marginBottom: 16 }}>
        <label>
          Status
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label>
          Severity
          <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}>
            <option value="">All</option>
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn btn-primary" onClick={() => setShowRaise(true)}>
          Raise Incident
        </button>
      </div>

      <div className="table-wrap">
        {isLoading ? (
          <p style={{ padding: 16 }}>Loading…</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Vehicle</th>
                <th>Created</th>
                <th>Assigned to</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((inc) => (
                <tr
                  key={inc.id}
                  onClick={() => {
                    setSelectedId(inc.id);
                    setToStatus(NEXT_STATUS[inc.status] || '');
                    setAssignUserId(inc.assigned_to ? String(inc.assigned_to) : '');
                  }}
                  style={{ cursor: 'pointer' }}
                >
                  <td>{inc.id}</td>
                  <td>{inc.type}</td>
                  <td>
                    <SeverityBadge severity={inc.severity} />
                  </td>
                  <td>{inc.status}</td>
                  <td>{inc.vehicle_id ? vehicleRegMap[inc.vehicle_id] || inc.vehicle_id : '—'}</td>
                  <td>{new Date(inc.created_at).toLocaleString()}</td>
                  <td>
                    {inc.assigned_to
                      ? assigneeOptions.find((u) => u.id === inc.assigned_to)?.name ||
                        `#${inc.assigned_to}`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showRaise && (
        <Modal title="Raise incident" onClose={() => setShowRaise(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              createMutation.mutate({
                type: raiseForm.type,
                severity: raiseForm.severity,
                description: raiseForm.description,
                depot_id: Number(raiseForm.depot_id),
                vehicle_id: raiseForm.vehicle_id ? Number(raiseForm.vehicle_id) : null,
              });
            }}
          >
            <div className="modal-field">
              <label>Type</label>
              <select
                value={raiseForm.type}
                onChange={(e) => setRaiseForm({ ...raiseForm, type: e.target.value })}
              >
                <option value="breakdown">Breakdown</option>
                <option value="accident">Accident</option>
                <option value="complaint">Complaint</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div className="modal-field">
              <label>Severity</label>
              <select
                value={raiseForm.severity}
                onChange={(e) => setRaiseForm({ ...raiseForm, severity: e.target.value })}
              >
                {SEVERITIES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div className="modal-field">
              <label>Depot ID</label>
              <input
                type="number"
                value={raiseForm.depot_id}
                onChange={(e) => setRaiseForm({ ...raiseForm, depot_id: e.target.value })}
              />
            </div>
            <div className="modal-field">
              <label>Vehicle (optional)</label>
              <select
                value={raiseForm.vehicle_id}
                onChange={(e) => setRaiseForm({ ...raiseForm, vehicle_id: e.target.value })}
              >
                <option value="">— None —</option>
                {vehicles.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.reg_no}
                  </option>
                ))}
              </select>
            </div>
            <div className="modal-field">
              <label>Description</label>
              <textarea
                rows={4}
                value={raiseForm.description}
                onChange={(e) => setRaiseForm({ ...raiseForm, description: e.target.value })}
                required
              />
            </div>
            <button type="submit" className="btn btn-primary">
              Submit
            </button>
          </form>
        </Modal>
      )}

      {selectedId && detail && (
        <Modal title={`Incident #${detail.id}`} onClose={() => setSelectedId(null)} wide>
          <p>
            <SeverityBadge severity={detail.severity} /> {detail.type} · <strong>{detail.status}</strong>
          </p>
          <p>{detail.description}</p>
          <p style={{ fontSize: 12, color: '#666' }}>
            Created {new Date(detail.created_at).toLocaleString()}
            {detail.vehicle_id && ` · Vehicle ${vehicleRegMap[detail.vehicle_id] || detail.vehicle_id}`}
          </p>

          <h3>Timeline</h3>
          <div className="timeline">
            {detail.events?.map((ev) => (
              <div key={ev.id} className="timeline-item">
                <div style={{ fontSize: 12, color: '#666' }}>{new Date(ev.ts).toLocaleString()}</div>
                <div>
                  {ev.from_status ? `${ev.from_status} → ` : ''}
                  <strong>{ev.to_status}</strong>
                </div>
                {ev.note && <div style={{ fontSize: 13 }}>{ev.note}</div>}
              </div>
            ))}
          </div>

          {canManage && nextForDetail && (
            <div style={{ marginTop: 16, borderTop: '1px solid #eee', paddingTop: 16 }}>
              <h3>Change status</h3>
              <div className="modal-field">
                <label>New status</label>
                <select value={toStatus} onChange={(e) => setToStatus(e.target.value)}>
                  <option value={nextForDetail}>{nextForDetail}</option>
                </select>
              </div>
              <div className="modal-field">
                <label>Note</label>
                <textarea
                  rows={2}
                  value={statusNote}
                  onChange={(e) => setStatusNote(e.target.value)}
                />
              </div>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() =>
                  statusMutation.mutate({
                    id: detail.id,
                    to_status: toStatus,
                    note: statusNote,
                  })
                }
              >
                Update status
              </button>
            </div>
          )}

          {canManage && (
            <div style={{ marginTop: 16, borderTop: '1px solid #eee', paddingTop: 16 }}>
              <h3>Assign to</h3>
              <div className="form-row">
                <select value={assignUserId} onChange={(e) => setAssignUserId(e.target.value)}>
                  <option value="">Select user</option>
                  {assigneeOptions.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.name}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!assignUserId}
                  onClick={() =>
                    assignMutation.mutate({
                      id: detail.id,
                      assigned_to: Number(assignUserId),
                    })
                  }
                >
                  Assign
                </button>
              </div>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}
