import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Navigate } from 'react-router-dom';
import client from '../api/client.js';
import { getUser } from '../api/auth.js';
import { weekStartIso } from '../utils/dates.js';

function countDutiesToday(roster, today) {
  if (!roster?.rows) return 0;
  let count = 0;
  for (const row of roster.rows) {
    if (row.cells?.[today]?.duty) count += 1;
  }
  return count;
}

export default function Dashboard() {
  const user = getUser();

  if (user?.role === 'driver') {
    return <Navigate to="/driver" replace />;
  }

  const isGlobal = user?.role === 'admin' || user?.role === 'control_operator';
  const depotId = user?.depot_id;
  const today = new Date().toISOString().slice(0, 10);
  const weekStart = weekStartIso();

  const { data: vehicles = [] } = useQuery({
    queryKey: ['dashboard-vehicles', depotId, isGlobal],
    queryFn: async () => {
      const params = isGlobal ? {} : { depot_id: depotId };
      const { data } = await client.get('/avls/vehicles', { params });
      return data;
    },
  });

  const { data: depotRoster } = useQuery({
    queryKey: ['dashboard-roster', depotId, weekStart],
    queryFn: async () => {
      const { data } = await client.get('/scheduling/roster', {
        params: { depot_id: depotId, week_start: weekStart },
      });
      return data;
    },
    enabled: !isGlobal && Boolean(depotId),
  });

  const { data: globalDutyCount = 0 } = useQuery({
    queryKey: ['dashboard-duties-global', weekStart, today],
    queryFn: async () => {
      let total = 0;
      for (let depot = 1; depot <= 4; depot += 1) {
        const { data } = await client.get('/scheduling/roster', {
          params: { depot_id: depot, week_start: weekStart },
        });
        total += countDutiesToday(data, today);
      }
      return total;
    },
    enabled: isGlobal,
  });

  const { data: incidents = [] } = useQuery({
    queryKey: ['dashboard-incidents', depotId, isGlobal],
    queryFn: async () => {
      const params = {};
      if (!isGlobal && depotId) params.depot_id = depotId;
      const { data } = await client.get('/incidents', { params });
      return data;
    },
  });

  const { data: notices = [] } = useQuery({
    queryKey: ['dashboard-notices'],
    queryFn: async () => {
      const { data } = await client.get('/cms/notices');
      return data;
    },
  });

  const totalVehicles = vehicles.length;
  const activeDutiesToday = isGlobal
    ? globalDutyCount
    : countDutiesToday(depotRoster, today);

  const openIncidents = incidents.filter(
    (i) => i.status === 'open' || i.status === 'in_progress',
  ).length;

  const unreadNotices = useMemo(() => {
    if (isGlobal) return notices.length;
    return notices.filter((n) => {
      const a = n.audience_json || {};
      return a.depot_ids?.includes(depotId) || a.depot_id === depotId;
    }).length;
  }, [notices, depotId, isGlobal]);

  const roleLabel = {
    admin: 'Administrator',
    depot_manager: 'Depot Manager',
    control_operator: 'Control Operator',
  }[user?.role] || user?.role;

  return (
    <div>
      <h1>Dashboard</h1>
      <p>
        Welcome, <strong>{user?.full_name}</strong> ({roleLabel})
        {!isGlobal && depotId != null && ` · Depot ${depotId}`}
      </p>

      <div className="card-grid" style={{ marginTop: 16 }}>
        <div className="stat-card">
          <h3>Total Vehicles</h3>
          <p>{totalVehicles}</p>
        </div>
        <div className="stat-card">
          <h3>Active Duties Today</h3>
          <p>{activeDutiesToday}</p>
        </div>
        <div className="stat-card">
          <h3>Open Incidents</h3>
          <p>{openIncidents}</p>
        </div>
        <div className="stat-card">
          <h3>Unread Notices</h3>
          <p>{unreadNotices}</p>
        </div>
      </div>
    </div>
  );
}
