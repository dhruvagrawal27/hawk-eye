import type { ReactElement, ReactNode } from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthContext, type AuthContextValue } from '@/auth/rbac'
import { TooltipProvider } from '@/components/ui/tooltip'
import {
  can as matrixCan,
  constraintFor as matrixConstraint,
  canViewCaseData as matrixCanViewCaseData,
} from '@/auth/capabilities'
import type { AuthUser, Role } from '@/lib/types'

/**
 * Test harness: render a component with Query + Router + a synthetic AuthContext for a chosen role,
 * so RBAC-dependent components (MaskedPII, EDD actions, role views) can be tested per the Part 24.1
 * matrix without the real login flow. The capability helpers come from the real matrix, so guards
 * behave exactly as in production.
 */
export function makeAuthValue(
  role: Role | null,
  overrides: Partial<AuthContextValue> = {},
): AuthContextValue {
  const user: AuthUser | null = role
    ? { sub: `test-${role}`, username: `${role}.test`, name: `Test ${role}`, roles: [role] }
    : null
  return {
    status: role ? 'authenticated' : 'unauthenticated',
    user,
    role,
    roles: role ? [role] : [],
    isMock: true,
    login: async () => {},
    completeSignin: async () => {},
    setActiveRole: () => {},
    logout: async () => {},
    can: (cap) => matrixCan(role ?? undefined, cap),
    constraintFor: (cap) => matrixConstraint(role ?? undefined, cap),
    canViewCaseData: matrixCanViewCaseData(role ?? undefined),
    ...overrides,
  }
}

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  })
}

interface ProviderOptions extends Omit<RenderOptions, 'wrapper'> {
  role?: Role | null
  route?: string
  authValue?: AuthContextValue
  queryClient?: QueryClient
}

export function renderWithProviders(ui: ReactElement, options: ProviderOptions = {}) {
  const { role = 'analyst', route = '/', authValue, queryClient, ...rest } = options
  const client = queryClient ?? makeQueryClient()
  const value = authValue ?? makeAuthValue(role)
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <AuthContext.Provider value={value}>
          <TooltipProvider delayDuration={0}>
            <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
          </TooltipProvider>
        </AuthContext.Provider>
      </QueryClientProvider>
    )
  }
  return { client, ...render(ui, { wrapper: Wrapper, ...rest }) }
}

export * from '@testing-library/react'
