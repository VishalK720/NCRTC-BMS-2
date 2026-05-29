import { useMemo, useState } from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import client from '../api/client.js';
import { getUser } from '../api/auth.js';
import Modal from '../components/Modal.jsx';
import { weekStartIso } from '../utils/dates.js';

function audienceLabel(audience) {
  if (!audience) return '—';
  if (audience.roles?.includes('driver') && !audience.depot_ids && !audience.depot_id) {
    return 'All drivers';
  }
  if (audience.depot_ids?.length) return `Depots: ${audience.depot_ids.join(', ')}`;
  if (audience.depot_id) return `Depot ${audience.depot_id}`;
  if (audience.roles?.length) return `Role: ${audience.roles.join(', ')}`;
  return JSON.stringify(audience);
}

export default function CMS() {
  const user = getUser();
  const qc = useQueryClient();
  const isAdmin = user?.role === 'admin';
  const depotId = user?.depot_id || 1;

  const [showCreate, setShowCreate] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [createForm, setCreateForm] = useState({
    title: '',
    body: '',
    audienceType: 'all_drivers',
    depot_id: String(depotId),
    role: 'driver',
    publish_date: new Date().toISOString().slice(0, 10),
  });

  const { data: notices = [], isLoading } = useQuery({
    queryKey: ['notices'],
    queryFn: async () => {
      const { data } = await client.get('/cms/notices');
      return data;
    },
  });

  const { data: roster } = useQuery({
    queryKey: ['cms-roster-count', depotId],
    queryFn: async () => {
      const { data } = await client.get('/scheduling/roster', {
        params: { depot_id: depotId, week_start: weekStartIso() },
      });
      return data;
    },
    enabled: isAdmin,
  });

  const totalDrivers = roster?.rows?.length ?? '—';

  const readQueries = useQueries({
    queries: notices.map((n) => ({
      queryKey: ['notice-reads', n.id],
      queryFn: async () => {
        const { data } = await client.get(`/cms/notices/${n.id}`);
        return data;
      },
      enabled: isAdmin,
    })),
  });

  const readCountById = useMemo(() => {
    const m = {};
    notices.forEach((n, i) => {
      m[n.id] = readQueries[i]?.data?.reads?.length ?? null;
    });
    return m;
  }, [notices, readQueries]);

  const { data: noticeDetail } = useQuery({
    queryKey: ['notice-detail', selectedId],
    queryFn: async () => {
      const { data } = await client.get(`/cms/notices/${selectedId}`);
      return data;
    },
    enabled: Boolean(selectedId),
  });

  const createMutation = useMutation({
    mutationFn: (body) => client.post('/cms/notices', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notices'] });
      setShowCreate(false);
    },
  });

  const buildAudience = () => {
    if (createForm.audienceType === 'all_drivers') return { roles: ['driver'] };
    if (createForm.audienceType === 'depot') return { depot_ids: [Number(createForm.depot_id)] };
    return { roles: [createForm.role] };
  };

  const submitCreate = (e) => {
    e.preventDefault();
    const publish_at = new Date(`${createForm.publish_date}T09:00:00`).toISOString();
    createMutation.mutate({
      title: createForm.title,
      body: createForm.body,
      audience_json: buildAudience(),
      publish_at,
    });
  };

  return (
    <div>
      <h1>CMS — Notices</h1>
      {isAdmin && (
        <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
          Create notice
        </button>
      )}

      {isLoading && <p>Loading…</p>}

      <div className="table-wrap" style={{ marginTop: 16 }}>
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Audience</th>
              <th>Publish at</th>
              {isAdmin && <th>Read count</th>}
            </tr>
          </thead>
          <tbody>
            {notices.map((n) => (
              <tr key={n.id} onClick={() => setSelectedId(n.id)} style={{ cursor: 'pointer' }}>
                <td>{n.title}</td>
                <td>{audienceLabel(n.audience_json)}</td>
                <td>{new Date(n.publish_at).toLocaleString()}</td>
                {isAdmin && (
                  <td>
                    {readCountById[n.id] ?? '…'} / {totalDrivers}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreate && isAdmin && (
        <Modal title="Create notice" onClose={() => setShowCreate(false)}>
          <form onSubmit={submitCreate}>
            <div className="modal-field">
              <label>Title</label>
              <input
                value={createForm.title}
                onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })}
                required
              />
            </div>
            <div className="modal-field">
              <label>Body</label>
              <textarea
                rows={5}
                value={createForm.body}
                onChange={(e) => setCreateForm({ ...createForm, body: e.target.value })}
                required
              />
            </div>
            <div className="modal-field">
              <label>Audience</label>
              <select
                value={createForm.audienceType}
                onChange={(e) => setCreateForm({ ...createForm, audienceType: e.target.value })}
              >
                <option value="all_drivers">All drivers</option>
                <option value="depot">Specific depot</option>
                <option value="role">Specific role</option>
              </select>
            </div>
            {createForm.audienceType === 'depot' && (
              <div className="modal-field">
                <label>Depot ID</label>
                <input
                  type="number"
                  value={createForm.depot_id}
                  onChange={(e) => setCreateForm({ ...createForm, depot_id: e.target.value })}
                />
              </div>
            )}
            {createForm.audienceType === 'role' && (
              <div className="modal-field">
                <label>Role</label>
                <select
                  value={createForm.role}
                  onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}
                >
                  <option value="driver">Driver</option>
                  <option value="conductor">Conductor</option>
                  <option value="depot_manager">Depot manager</option>
                  <option value="control_operator">Control operator</option>
                </select>
              </div>
            )}
            <div className="modal-field">
              <label>Publish date</label>
              <input
                type="date"
                value={createForm.publish_date}
                onChange={(e) => setCreateForm({ ...createForm, publish_date: e.target.value })}
              />
            </div>
            <button type="submit" className="btn btn-primary">
              Create
            </button>
          </form>
        </Modal>
      )}

      {selectedId && noticeDetail && (
        <Modal title={noticeDetail.title} onClose={() => setSelectedId(null)} wide>
          <p style={{ fontSize: 12, color: '#666' }}>
            {audienceLabel(noticeDetail.audience_json)} ·{' '}
            {new Date(noticeDetail.publish_at).toLocaleString()}
          </p>
          <p style={{ whiteSpace: 'pre-wrap' }}>{noticeDetail.body}</p>
          {isAdmin && (
            <>
              <h3>Read receipts</h3>
              {noticeDetail.reads?.length === 0 && <p>No reads yet.</p>}
              <ul style={{ paddingLeft: 0, listStyle: 'none' }}>
                {noticeDetail.reads?.map((r) => (
                  <li
                    key={`${r.notice_id}-${r.user_id}`}
                    style={{ padding: '6px 0', borderBottom: '1px solid #eee' }}
                  >
                    {r.full_name || r.username || `User ${r.user_id}`} —{' '}
                    {new Date(r.read_at).toLocaleString()}
                  </li>
                ))}
              </ul>
            </>
          )}
        </Modal>
      )}
    </div>
  );
}
