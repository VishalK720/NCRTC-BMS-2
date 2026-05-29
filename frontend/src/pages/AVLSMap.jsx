import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MapContainer, TileLayer, Marker, Tooltip, Polyline } from 'react-leaflet';
import L from 'leaflet';
import client from '../api/client.js';
import { getUser } from '../api/auth.js';

const DELHI_CENTER = [28.6139, 77.209];
const DEFAULT_ZOOM = 11;

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function weekStartIso(d = new Date()) {
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  const monday = new Date(d);
  monday.setDate(d.getDate() + diff);
  return monday.toISOString().slice(0, 10);
}

function pingsToLatLngs(pings) {
  return pings.map((p) => [p.lat, p.lng]);
}

export default function AVLSMap() {
  const user = getUser();
  const [depotFilter, setDepotFilter] = useState(user?.depot_id ? String(user.depot_id) : '');
  const [selectedVehicle, setSelectedVehicle] = useState(null);
  const [panelTab, setPanelTab] = useState('live');
  const [historyDate, setHistoryDate] = useState(todayIso());
  const [historyVehicleId, setHistoryVehicleId] = useState('');

  const { data: vehicles = [], isLoading } = useQuery({
    queryKey: ['avls-vehicles', depotFilter],
    queryFn: async () => {
      const params = depotFilter ? { depot_id: Number(depotFilter) } : {};
      const { data } = await client.get('/avls/vehicles', { params });
      return data;
    },
    refetchInterval: 8000,
  });

  const depotOptions = useMemo(() => {
    const ids = [...new Set(vehicles.map((v) => v.depot_id))].sort((a, b) => a - b);
    return ids;
  }, [vehicles]);

  const selectedId = selectedVehicle?.id;

  const { data: livePings = [] } = useQuery({
    queryKey: ['avls-pings', selectedId],
    queryFn: async () => {
      const { data } = await client.get(`/avls/vehicles/${selectedId}/pings`);
      return data;
    },
    enabled: Boolean(selectedId) && panelTab === 'live',
    refetchInterval: panelTab === 'live' ? 8000 : false,
  });

  const historyVid = historyVehicleId || selectedId;
  const { data: historyPings = [] } = useQuery({
    queryKey: ['avls-history', historyVid, historyDate],
    queryFn: async () => {
      const { data } = await client.get(`/avls/vehicles/${historyVid}/history`, {
        params: { date: historyDate },
      });
      return data;
    },
    enabled: Boolean(historyVid) && panelTab === 'history',
  });

  const { data: dutyInfo } = useQuery({
    queryKey: ['roster-duty', selectedVehicle?.depot_id, selectedId],
    queryFn: async () => {
      const { data } = await client.get('/scheduling/roster', {
        params: {
          depot_id: selectedVehicle.depot_id,
          week_start: weekStartIso(),
        },
      });
      const today = todayIso();
      for (const row of data.rows) {
        const cell = row.cells[today];
        if (cell?.duty?.vehicle_id === selectedId) {
          return {
            driver_name: row.driver_name,
            route_code: cell.duty.route_code,
            route_id: cell.duty.route_id,
          };
        }
      }
      return null;
    },
    enabled: Boolean(selectedId && selectedVehicle?.depot_id),
  });

  const livePolyline = pingsToLatLngs(livePings);
  const historyPolyline = pingsToLatLngs(historyPings);

  const mapVehicles = vehicles.filter((v) => v.latest_ping);

  return (
    <div className="map-page" style={{ margin: '-16px', height: 'calc(100vh - 52px)' }}>
      <div className="map-wrap">
        <div className="map-inner">
          <div className="map-overlay-filter">
            <label>
              Depot{' '}
              <select value={depotFilter} onChange={(e) => setDepotFilter(e.target.value)}>
                <option value="">All</option>
                {depotOptions.map((id) => (
                  <option key={id} value={id}>
                    Depot {id}
                  </option>
                ))}
              </select>
            </label>
            {isLoading && <span style={{ marginLeft: 8 }}>Updating…</span>}
          </div>

          <MapContainer
            center={DELHI_CENTER}
            zoom={DEFAULT_ZOOM}
            style={{ height: '100%', width: '100%' }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {mapVehicles.map((v) => (
              <Marker
                key={v.id}
                position={[v.latest_ping.lat, v.latest_ping.lng]}
                eventHandlers={{
                  click: () => {
                    setSelectedVehicle(v);
                    setHistoryVehicleId(String(v.id));
                    setPanelTab('live');
                  },
                }}
              >
                <Tooltip>
                  {v.reg_no} · {v.latest_ping.speed_kmh ?? '—'} km/h
                </Tooltip>
              </Marker>
            ))}

            {panelTab === 'live' && livePolyline.length > 1 && (
              <Polyline positions={livePolyline} color="#1565c0" weight={4} />
            )}
            {panelTab === 'history' && historyPolyline.length > 1 && (
              <Polyline positions={historyPolyline} color="#e65100" weight={4} />
            )}
          </MapContainer>
        </div>

        {selectedVehicle && (
          <aside className="map-panel">
            <div className="map-panel-body">
              <button
                type="button"
                className="btn"
                style={{ float: 'right' }}
                onClick={() => setSelectedVehicle(null)}
              >
                ×
              </button>
              <h3 style={{ marginTop: 0 }}>{selectedVehicle.reg_no}</h3>
              <p>
                <strong>Depot:</strong> {selectedVehicle.depot_id}
              </p>
              <p>
                <strong>Driver:</strong> {dutyInfo?.driver_name || '—'}
              </p>
              <p>
                <strong>Route:</strong> {dutyInfo?.route_code || '—'}
              </p>
              {selectedVehicle.latest_ping && (
                <p>
                  <strong>Speed:</strong> {selectedVehicle.latest_ping.speed_kmh ?? '—'} km/h
                  <br />
                  <strong>Last ping:</strong>{' '}
                  {new Date(selectedVehicle.latest_ping.ts).toLocaleString()}
                </p>
              )}

              {panelTab === 'live' && (
                <p style={{ fontSize: 12, color: '#666' }}>
                  Blue line: last 30 min ({livePings.length} points)
                </p>
              )}

              {panelTab === 'history' && (
                <div style={{ marginTop: 12 }}>
                  <div className="form-row" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                    <label>
                      Vehicle
                      <select
                        value={historyVehicleId}
                        onChange={(e) => setHistoryVehicleId(e.target.value)}
                        style={{ width: '100%' }}
                      >
                        {vehicles.map((v) => (
                          <option key={v.id} value={v.id}>
                            {v.reg_no}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Date
                      <input
                        type="date"
                        value={historyDate}
                        onChange={(e) => setHistoryDate(e.target.value)}
                        style={{ width: '100%' }}
                      />
                    </label>
                  </div>
                  <p style={{ fontSize: 12, color: '#666' }}>
                    Orange line: {historyPings.length} points on {historyDate}
                  </p>
                </div>
              )}
            </div>
            <div className="map-tabs">
              <button
                type="button"
                className={panelTab === 'live' ? 'active' : ''}
                onClick={() => setPanelTab('live')}
              >
                Live
              </button>
              <button
                type="button"
                className={panelTab === 'history' ? 'active' : ''}
                onClick={() => setPanelTab('history')}
              >
                History
              </button>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
