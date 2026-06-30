import { lazy } from 'react'
import { createBrowserRouter } from 'react-router-dom'
import { RequireAuth } from '@/auth/rbac'
import { RoleShell } from '@/auth/RoleShell'
import { LoginPage } from '@/auth/LoginPage'
import { CallbackPage } from '@/auth/CallbackPage'
import { AppLayout } from './AppLayout'
import { Dashboard } from './Dashboard'
import { Forbidden } from './Forbidden'
import { NotFound } from './NotFound'
import { ROUTE_ROLES } from './nav-config'

/* Route-lazy the heavy investigation screens so the initial bundle stays small (Part 11 perf budget). */
const TriageQueue = lazy(() =>
  import('@/views/TriageQueue').then((m) => ({ default: m.TriageQueue })),
)
const AlertDetail = lazy(() =>
  import('@/views/AlertDetail').then((m) => ({ default: m.AlertDetail })),
)
const CaseManagement = lazy(() =>
  import('@/views/CaseManagement').then((m) => ({ default: m.CaseManagement })),
)
const CaseDetailShell = lazy(() =>
  import('@/views/CaseDetailShell').then((m) => ({ default: m.CaseDetailShell })),
)
const ComplianceView = lazy(() =>
  import('@/views/ComplianceView').then((m) => ({ default: m.ComplianceView })),
)
const AuditorView = lazy(() =>
  import('@/views/AuditorView').then((m) => ({ default: m.AuditorView })),
)
const ModelEngineerView = lazy(() =>
  import('@/views/ModelEngineerView').then((m) => ({ default: m.ModelEngineerView })),
)
const AdminView = lazy(() => import('@/views/AdminView').then((m) => ({ default: m.AdminView })))
const ReportingView = lazy(() =>
  import('@/views/ReportingView').then((m) => ({ default: m.ReportingView })),
)

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/auth/callback', element: <CallbackPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <Dashboard /> },
          { path: 'forbidden', element: <Forbidden /> },

          // Triage + cases (Analyst home, Part 24.4 screens 2 & 4)
          {
            element: <RoleShell roles={ROUTE_ROLES.triageAndCases} />,
            children: [
              { path: 'triage', element: <TriageQueue /> },
              { path: 'cases', element: <CaseManagement /> },
              { path: 'cases/:caseId', element: <CaseDetailShell /> },
            ],
          },

          // Alert / case detail — the workhorse screen (Part 24.4 screen 3). Case-data viewers only.
          {
            element: <RoleShell roles={ROUTE_ROLES.caseDetailViewers} />,
            children: [{ path: 'alerts/:alertId', element: <AlertDetail /> }],
          },

          // Compliance (screen 5)
          {
            element: <RoleShell roles={ROUTE_ROLES.compliance} />,
            children: [{ path: 'compliance', element: <ComplianceView /> }],
          },

          // Auditor (screen 6)
          {
            element: <RoleShell roles={ROUTE_ROLES.audit} />,
            children: [{ path: 'audit', element: <AuditorView /> }],
          },

          // Model engineer (screen 7)
          {
            element: <RoleShell roles={ROUTE_ROLES.models} />,
            children: [{ path: 'models', element: <ModelEngineerView /> }],
          },

          // Reporting & board KRIs
          {
            element: <RoleShell roles={ROUTE_ROLES.reporting} />,
            children: [{ path: 'reporting', element: <ReportingView /> }],
          },

          // Admin (screen 8)
          {
            element: <RoleShell roles={ROUTE_ROLES.admin} />,
            children: [{ path: 'admin', element: <AdminView /> }],
          },

          { path: '*', element: <NotFound /> },
        ],
      },
    ],
  },
])
