import { Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import MdmPage from '@/pages/MdmPage'
import SalesPage from '@/pages/SalesPage'
import ScmPage from '@/pages/ScmPage'
import ProcurementPage from '@/pages/ProcurementPage'
import LogisticsPage from '@/pages/LogisticsPage'
import QualityPage from '@/pages/QualityPage'
import ProductionPage from '@/pages/ProductionPage'
import InventoryPage from '@/pages/InventoryPage'
import FinancePage from '@/pages/FinancePage'
import ApprovalsPage from '@/pages/ApprovalsPage'
import IntegrationsPage from '@/pages/IntegrationsPage'
import AiAgentPage from '@/pages/AiAgentPage'
import ReferenceDataPage from '@/pages/ReferenceDataPage'
import ProtectedRoute from '@/components/ProtectedRoute'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/mdm" element={<MdmPage />} />
        <Route path="/sales" element={<SalesPage />} />
        <Route path="/scm" element={<ScmPage />} />
        <Route path="/procurement" element={<ProcurementPage />} />
        <Route path="/logistics" element={<LogisticsPage />} />
        <Route path="/quality" element={<QualityPage />} />
        <Route path="/production" element={<ProductionPage />} />
        <Route path="/inventory" element={<InventoryPage />} />
        <Route path="/finance" element={<FinancePage />} />
        <Route path="/approvals" element={<ApprovalsPage />} />
        <Route path="/integrations" element={<IntegrationsPage />} />
        <Route path="/ai-agent" element={<AiAgentPage />} />
        <Route path="/reference" element={<ReferenceDataPage />} />
      </Route>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
