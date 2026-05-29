import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import client from '../api/client.js';
import { clearAuth, getUser } from '../api/auth.js';
import Modal from '../components/Modal.jsx';

function readStorageKey(userId) {
  return `notice_reads_${userId}`;
}

function getLocalReads(userId) {
  try {
    return JSON.parse(localStorage.getItem(readStorageKey(userId)) || '[]');
  } catch {
    return [];
  }
}

function addLocalRead(userId, noticeId) {
  const ids = getLocalReads(userId);
  if (!ids.includes(noticeId)) {
    localStorage.setItem(readStorageKey(userId), JSON.stringify([...ids, noticeId]));
  }
}

export default function DriverApp() {
  const user = getUser();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [openNotice, setOpenNotice] = useState(null);
  const [toast, setToast] = useState('');
  const [localReads, setLocalReads] = useState(() => getLocalReads(user?.id));

  useEffect(() => {
    if (!toast) return undefined;
    const t = setTimeout(() => setToast(''), 3000);
    return () => clearTimeout(t);
  }, [toast]);

  const { data: duty, isLoading: dutyLoading } = useQuery({
    queryKey: ['my-duty'],
    queryFn: async () => {
      const { data } = await client.get('/scheduling/my-duty');
      return data;
    },
  });

  const { data: notices = [] } = useQuery({
    queryKey: ['notices-driver'],
    queryFn: async () => {
      const { data } = await client.get('/cms/notices');
      return data;
    },
  });

  const unreadNotices = useMemo(() => {
    return notices.filter((n) => !localReads.includes(n.id));
  }, [notices, localReads]);

  const ackMutation = useMutation({
    mutationFn: (dutyId) => client.put(`/scheduling/duties/${dutyId}/acknowledge`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['my-duty'] }),
  });

  const panicMutation = useMutation({
    mutationFn: () => client.post('/incidents/panic'),
    onSuccess: () => setToast('P1 emergency incident created successfully'),
    onError: (err) => setToast(err.response?.data?.detail || 'Panic request failed'),
  });

  const readMutation = useMutation({
    mutationFn: (id) => client.post(`/cms/notices/${id}/read`),
    onSuccess: (_, noticeId) => {
      addLocalRead(user.id, noticeId);
      setLocalReads(getLocalReads(user.id));
      qc.invalidateQueries({ queryKey: ['notices-driver'] });
    },
  });

  const openNoticeDetail = (notice) => {
    setOpenNotice(notice);
    readMutation.mutate(notice.id);
  };

  const logout = () => {
    clearAuth();
    navigate('/login');
  };

  const showAck =
    duty && duty.status === 'published' && !duty.ack_at;

  return (
    <div className="driver-app">
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ marginBottom: 4 }}>{user?.full_name}</h1>
          <p style={{ margin: 0, color: '#666', fontSize: 13 }}>
            Depot {user?.depot_id ?? '—'}
          </p>
        </div>
        <button type="button" className="btn" onClick={logout}>
          Logout
        </button>
      </header>

      <section style={{ marginTop: 20 }}>
        <h2 style={{ fontSize: 16, marginTop: 0 }}>Today&apos;s duty</h2>
        {dutyLoading && <p>Loading…</p>}
        {!dutyLoading && !duty && <p>No duty assigned for today.</p>}
        {duty && (
          <div style={{ border: '1px solid #ddd', padding: 14, borderRadius: 4 }}>
            <p style={{ margin: '0 0 8px' }}>
              <strong>Vehicle:</strong> {duty.vehicle_reg_no || duty.vehicle_id}
            </p>
            <p style={{ margin: '0 0 8px' }}>
              <strong>Route:</strong> {duty.route_code || duty.route_id}
            </p>
            <p style={{ margin: '0 0 8px' }}>
              <strong>Start:</strong> {String(duty.start_time).slice(0, 5)}
            </p>
            <p style={{ margin: '0 0 8px' }}>
              <span className="badge badge-published">{duty.status}</span>
            </p>
            {showAck && (
              <button
                type="button"
                className="btn btn-primary"
                style={{ width: '100%', marginTop: 8 }}
                onClick={() => ackMutation.mutate(duty.id)}
                disabled={ackMutation.isPending}
              >
                Acknowledge
              </button>
            )}
          </div>
        )}
      </section>

      <section style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: 16 }}>Unread notices ({unreadNotices.length})</h2>
        {unreadNotices.length === 0 && <p style={{ color: '#666' }}>No unread notices.</p>}
        {unreadNotices.map((n) => (
          <div
            key={n.id}
            className="notice-unread"
            style={{ padding: 12, marginBottom: 8, background: '#f9f9f9' }}
            onClick={() => openNoticeDetail(n)}
          >
            <strong>{n.title}</strong>
            <p style={{ margin: '4px 0 0', fontSize: 13, color: '#666' }}>
              {new Date(n.publish_at).toLocaleDateString()}
            </p>
          </div>
        ))}
      </section>

      <div style={{ marginTop: 32, paddingBottom: 24 }}>
        <button
          type="button"
          className="btn btn-danger"
          style={{ width: '100%', padding: 18, fontSize: 18, fontWeight: 'bold' }}
          disabled={panicMutation.isPending}
          onClick={() => {
            if (window.confirm('Create P1 emergency incident?')) {
              panicMutation.mutate();
            }
          }}
        >
          PANIC
        </button>
      </div>

      {openNotice && (
        <Modal title={openNotice.title} onClose={() => setOpenNotice(null)}>
          <p style={{ whiteSpace: 'pre-wrap' }}>{openNotice.body}</p>
        </Modal>
      )}

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
