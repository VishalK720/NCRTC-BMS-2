import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute.jsx';
import Layout from './components/Layout.jsx';
import Login from './pages/Login.jsx';
import Dashboard from './pages/Dashboard.jsx';
import AVLSMap from './pages/AVLSMap.jsx';
import Scheduling from './pages/Scheduling.jsx';
import Incidents from './pages/Incidents.jsx';
import CMS from './pages/CMS.jsx';
import DriverApp from './pages/DriverApp.jsx';

function ProtectedLayout({ children }) {
  return (
    <ProtectedRoute>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedLayout>
            <Dashboard />
          </ProtectedLayout>
        }
      />
      <Route
        path="/map"
        element={
          <ProtectedLayout>
            <AVLSMap />
          </ProtectedLayout>
        }
      />
      <Route
        path="/scheduling"
        element={
          <ProtectedLayout>
            <Scheduling />
          </ProtectedLayout>
        }
      />
      <Route
        path="/incidents"
        element={
          <ProtectedLayout>
            <Incidents />
          </ProtectedLayout>
        }
      />
      <Route
        path="/cms"
        element={
          <ProtectedLayout>
            <CMS />
          </ProtectedLayout>
        }
      />
      <Route
        path="/driver"
        element={
          <ProtectedRoute>
            <DriverApp />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
