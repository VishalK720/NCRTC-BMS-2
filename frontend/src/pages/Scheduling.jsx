import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import client from '../api/client.js';
import { getUser } from '../api/auth.js';
import Modal from '../components/Modal.jsx';
import { weekDates, weekStartIso } from '../utils/dates.js';

const emptyRoute = { code: '', name: '', depot_id: '' };

export default function Scheduling() {
  const user = getUser();
  const qc = useQueryClient();
  const isAdmin = user?.role === 'admin';
  const isManager = user?.role === 'depot_manager' || isAdmin;

  const [depotId, setDepotId] = useState(user?.depot_id || 1);
  const [weekStart, setWeekStart] = useState(weekStartIso());
  const [routeModal, setRouteModal] = useState(null);
  const [routeForm, setRouteForm] = useState(emptyRoute);
  const [assignModal, setAssignModal] = useState(null);

  const days = useMemo(() => weekDates(weekStart), [weekStart]);

  const { data: roster, isLoading: rosterLoading } = useQuery({
    queryKey: ['roster', depotId, weekStart],
    queryFn: async () => {
      const { data } = await client.get('/scheduling/roster', {
        params: { depot_id: depotId, week_start: weekStart },
      });
      return data;
    },
    enabled: Boolean(depotId),
  });

  const { data: routes = [] } = useQuery({
    queryKey: ['routes', depotId],
    queryFn: async () => {
      const { data } = await client.get('/routes', { params: { depot_id: depotId } });
      return data;
    },
    enabled: Boolean(depotId),
  });

  const { data: vehicles = [] } = useQuery({
    queryKey: ['vehicles', depotId],
    queryFn: async () => {
      const { data } = await client.get('/avls/vehicles', { params: { depot_id: depotId } });
      return data;
    },
    enabled: Boolean(depotId),
  });

  const publishMutation = useMutation({
    mutationFn: (dutyId) => client.put(`/scheduling/duties/${dutyId}/publish`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['roster'] }),
  });

  const createRouteMutation = useMutation({
    mutationFn: (body) => client.post('/routes', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['routes'] });
      setRouteModal(null);
    },
  });

  const updateRouteMutation = useMutation({
    mutationFn: ({ id, body }) => client.put(`/routes/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['routes'] });
      setRouteModal(null);
    },
  });

  const deleteRouteMutation = useMutation({
    mutationFn: (id) => client.delete(`/routes/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['routes'] }),
  });

  const assignMutation = useMutation({
    mutationFn: (body) => client.post('/scheduling/duties', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['roster'] });
      setAssignModal(null);
    },
  });

  const openCreateRoute = () => {
    setRouteForm({ code: '', name: '', depot_id: String(depotId) });
    setRouteModal('create');
  };

  const openEditRoute = (route) => {
    setRouteForm({ code: route.code, name: route.name, depot_id: String(route.depot_id) });
    setRouteModal({ edit: route.id });
  };

  const openAssign = (row, dateIso) => {
    const other = roster?.rows?.find((r) => r.driver_id !== row.driver_id);
    setAssignModal({
      driver_id: row.driver_id,
      driver_name: row.driver_name,
      date: dateIso,
      vehicle_id: vehicles[0]?.id ? String(vehicles[0].id) : '',
      route_id: routes[0]?.id ? String(routes[0].id) : '',
      conductor_id: other?.driver_id ?? row.driver_id,
      start_time: '06:00:00',
      end_time: '14:00:00',
    });
  };

  const submitRoute = (e) => {
    e.preventDefault();
    const body = {
      code: routeForm.code,
      name: routeForm.name,
      depot_id: Number(routeForm.depot_id),
      stops: [],
    };
    if (routeModal === 'create') {
      createRouteMutation.mutate(body);
    } else if (routeModal?.edit) {
      updateRouteMutation.mutate({ id: routeModal.edit, body });
    }
  };

  const submitAssign = (e) => {
    e.preventDefault();
    assignMutation.mutate({
      date: assignModal.date,
      vehicle_id: Number(assignModal.vehicle_id),
      driver_id: Number(assignModal.driver_id),
      conductor_id: Number(assignModal.conductor_id),
      route_id: Number(assignModal.route_id),
      start_time: assignModal.start_time,
      end_time: assignModal.end_time,
    });
  };

  return (
    <div>
      <h1>Scheduling</h1>
      <div className="form-row">
        <label>
          Depot ID
          <input
            type="number"
            value={depotId}
            onChange={(e) => setDepotId(Number(e.target.value))}
            min={1}
          />
        </label>
        <label>
          Week (Mon)
          <input type="date" value={weekStart} onChange={(e) => setWeekStart(e.target.value)} />
        </label>
      </div>

      <section style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: 16 }}>Routes</h2>
          {isAdmin && (
            <button type="button" className="btn btn-primary" onClick={openCreateRoute}>
              Create route
            </button>
          )}
        </div>
        <div className="table-wrap" style={{ marginTop: 8 }}>
          <table>
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Depot</th>
                {isAdmin && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {routes.map((r) => (
                <tr key={r.id}>
                  <td>{r.code}</td>
                  <td>{r.name}</td>
                  <td>{r.depot_id}</td>
                  {isAdmin && (
                    <td>
                      <button type="button" className="btn" onClick={() => openEditRoute(r)}>
                        Edit
                      </button>{' '}
                      <button
                        type="button"
                        className="btn"
                        onClick={() => {
                          if (window.confirm(`Delete route ${r.code}?`)) {
                            deleteRouteMutation.mutate(r.id);
                          }
                        }}
                      >
                        Delete
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 style={{ fontSize: 16 }}>Roster</h2>
        {rosterLoading && <p>Loading roster…</p>}
        {roster && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Driver</th>
                  {days.map((d) => (
                    <th key={d.iso}>
                      {d.label}
                      <br />
                      <span style={{ fontWeight: 'normal', fontSize: 11 }}>{d.iso.slice(5)}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {roster.rows.map((row) => (
                  <tr key={row.driver_id}>
                    <td>{row.driver_name}</td>
                    {days.map((d) => {
                      const duty = row.cells[d.iso]?.duty;
                      return (
                        <td key={d.iso} className="roster-cell">
                          {duty ? (
                            <>
                              <div>{duty.vehicle_reg_no || `V${duty.vehicle_id}`}</div>
                              <div>{duty.route_code || `R${duty.route_id}`}</div>
                              {duty.status === 'published' ||
                              duty.status === 'acknowledged' ||
                              duty.status === 'completed' ? (
                                <span className="badge badge-published">Published</span>
                              ) : duty.status === 'draft' && isManager ? (
                                <button
                                  type="button"
                                  className="btn"
                                  style={{ fontSize: 10, marginTop: 4, padding: '2px 6px' }}
                                  onClick={() => publishMutation.mutate(duty.id)}
                                >
                                  Publish
                                </button>
                              ) : (
                                <em>{duty.status}</em>
                              )}
                            </>
                          ) : (
                            isManager && (
                              <button
                                type="button"
                                className="btn"
                                style={{ fontSize: 11, padding: '4px 8px' }}
                                onClick={() => openAssign(row, d.iso)}
                              >
                                Assign
                              </button>
                            )
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {routeModal && (
        <Modal
          title={routeModal === 'create' ? 'Create route' : 'Edit route'}
          onClose={() => setRouteModal(null)}
        >
          <form onSubmit={submitRoute}>
            <div className="modal-field">
              <label>Code</label>
              <input
                value={routeForm.code}
                onChange={(e) => setRouteForm({ ...routeForm, code: e.target.value })}
                required
              />
            </div>
            <div className="modal-field">
              <label>Name</label>
              <input
                value={routeForm.name}
                onChange={(e) => setRouteForm({ ...routeForm, name: e.target.value })}
                required
              />
            </div>
            <div className="modal-field">
              <label>Depot ID</label>
              <input
                type="number"
                value={routeForm.depot_id}
                onChange={(e) => setRouteForm({ ...routeForm, depot_id: e.target.value })}
                required
              />
            </div>
            <button type="submit" className="btn btn-primary">
              Save
            </button>
          </form>
        </Modal>
      )}

      {assignModal && (
        <Modal title="Assign duty" onClose={() => setAssignModal(null)}>
          <form onSubmit={submitAssign}>
            <div className="modal-field">
              <label>Driver</label>
              <input value={assignModal.driver_name} disabled />
            </div>
            <div className="modal-field">
              <label>Date</label>
              <input
                type="date"
                value={assignModal.date}
                onChange={(e) => setAssignModal({ ...assignModal, date: e.target.value })}
                required
              />
            </div>
            <div className="modal-field">
              <label>Vehicle</label>
              <select
                value={assignModal.vehicle_id}
                onChange={(e) => setAssignModal({ ...assignModal, vehicle_id: e.target.value })}
                required
              >
                {vehicles.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.reg_no}
                  </option>
                ))}
              </select>
            </div>
            <div className="modal-field">
              <label>Route</label>
              <select
                value={assignModal.route_id}
                onChange={(e) => setAssignModal({ ...assignModal, route_id: e.target.value })}
                required
              >
                {routes.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.code} — {r.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="modal-field">
              <label>Conductor (driver ID)</label>
              <select
                value={assignModal.conductor_id}
                onChange={(e) =>
                  setAssignModal({ ...assignModal, conductor_id: Number(e.target.value) })
                }
              >
                {roster?.rows?.map((r) => (
                  <option key={r.driver_id} value={r.driver_id}>
                    {r.driver_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-row">
              <div className="modal-field" style={{ flex: 1 }}>
                <label>Start</label>
                <input
                  type="time"
                  value={assignModal.start_time.slice(0, 5)}
                  onChange={(e) =>
                    setAssignModal({ ...assignModal, start_time: `${e.target.value}:00` })
                  }
                />
              </div>
              <div className="modal-field" style={{ flex: 1 }}>
                <label>End</label>
                <input
                  type="time"
                  value={assignModal.end_time.slice(0, 5)}
                  onChange={(e) =>
                    setAssignModal({ ...assignModal, end_time: `${e.target.value}:00` })
                  }
                />
              </div>
            </div>
            <button type="submit" className="btn btn-primary" disabled={assignMutation.isPending}>
              Create duty
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}
