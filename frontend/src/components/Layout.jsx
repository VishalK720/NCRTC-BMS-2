import { NavLink, useNavigate } from 'react-router-dom';
import { clearAuth, getUser } from '../api/auth.js';

export default function Layout({ children }) {
  const navigate = useNavigate();
  const user = getUser();

  const logout = () => {
    clearAuth();
    navigate('/login');
  };

  return (
    <div className="app-shell">
      <nav className="app-nav">
        <strong>NCRTC BMS</strong>
        <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : '')}>
          Dashboard
        </NavLink>
        <NavLink to="/map" className={({ isActive }) => (isActive ? 'active' : '')}>
          Map
        </NavLink>
        <NavLink to="/scheduling" className={({ isActive }) => (isActive ? 'active' : '')}>
          Scheduling
        </NavLink>
        <NavLink to="/incidents" className={({ isActive }) => (isActive ? 'active' : '')}>
          Incidents
        </NavLink>
        <NavLink to="/cms" className={({ isActive }) => (isActive ? 'active' : '')}>
          CMS
        </NavLink>
        <span className="spacer" />
        <span>{user?.full_name || user?.username}</span>
        <button type="button" className="btn" onClick={logout}>
          Logout
        </button>
      </nav>
      <main className="app-main">{children}</main>
    </div>
  );
}
