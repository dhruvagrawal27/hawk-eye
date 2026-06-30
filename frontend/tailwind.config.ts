import type { Config } from 'tailwindcss'
import animate from 'tailwindcss-animate'

// Hawk-Eye design system (blueprint Part 11 — investigator console).
// shadcn/ui token model: semantic colours resolve to CSS variables defined in src/index.css,
// so light/dark themes flip by toggling the `.dark` class. Domain colours (severity, risk, layer,
// reason-code source) are added on top so the whole UI speaks one visual language.
const config: Config = {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    container: {
      center: true,
      padding: '1.5rem',
      screens: { '2xl': '1480px' },
    },
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar))',
          foreground: 'hsl(var(--sidebar-foreground))',
          accent: 'hsl(var(--sidebar-accent))',
          border: 'hsl(var(--sidebar-border))',
        },
        // Domain palette — severity / risk bands (Part 24.4 triage + header).
        severity: {
          critical: 'hsl(var(--severity-critical))',
          high: 'hsl(var(--severity-high))',
          medium: 'hsl(var(--severity-medium))',
          low: 'hsl(var(--severity-low))',
          info: 'hsl(var(--severity-info))',
        },
        // SLA / TAT timer bands (green → amber → red → breached).
        sla: {
          ok: 'hsl(var(--sla-ok))',
          warn: 'hsl(var(--sla-warn))',
          urgent: 'hsl(var(--sla-urgent))',
          breached: 'hsl(var(--sla-breached))',
        },
        // Reason-code provenance (rule / shap / graph) + AI/TEE accents.
        reason: {
          rule: 'hsl(var(--reason-rule))',
          shap: 'hsl(var(--reason-shap))',
          graph: 'hsl(var(--reason-graph))',
        },
        ai: 'hsl(var(--ai))',
        tee: 'hsl(var(--tee))',
        // Terminal risk scale — single source for badges/numbers/dots/rows/nodes/charts.
        // Aliases the severity tokens so the whole UI reads one palette (useRiskColor()).
        risk: {
          low: 'hsl(var(--severity-low))',
          medium: 'hsl(var(--severity-medium))',
          high: 'hsl(var(--severity-high))',
          critical: 'hsl(var(--severity-critical))',
          flat: 'hsl(var(--risk-flat))',
        },
        // Bloomberg-tape cyan accent (status bar / event ticker).
        ticker: 'hsl(var(--ticker))',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        sans: ['"Inter Variable"', 'Inter var', 'Inter', 'system-ui', 'sans-serif'],
        mono: [
          '"JetBrains Mono Variable"',
          '"JetBrains Mono"',
          'ui-monospace',
          'SFMono-Regular',
          'monospace',
        ],
      },
      fontSize: {
        // micro sizes for terminal eyebrows / tape rows / dense labels
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }], // 10px
        '3xs': ['0.5625rem', { lineHeight: '0.75rem' }], // 9px
      },
      letterSpacing: {
        widest: '0.18em',
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
        'pulse-urgent': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.45' },
        },
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        // terminal: soft live-dot pulse + green/red freshness flash for the event tape
        'pulse-soft': {
          '0%, 100%': { opacity: '0.55' },
          '50%': { opacity: '1' },
        },
        'tick-up': {
          '0%': { backgroundColor: 'hsl(var(--severity-low) / 0.35)' },
          '100%': { backgroundColor: 'transparent' },
        },
        'tick-down': {
          '0%': { backgroundColor: 'hsl(var(--severity-critical) / 0.35)' },
          '100%': { backgroundColor: 'transparent' },
        },
        'row-flash': {
          '0%': { backgroundColor: 'hsl(var(--ticker) / 0.22)' },
          '100%': { backgroundColor: 'transparent' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'pulse-urgent': 'pulse-urgent 1.4s ease-in-out infinite',
        'fade-in': 'fade-in 0.18s ease-out',
        'pulse-soft': 'pulse-soft 2s ease-in-out infinite',
        'tick-up': 'tick-up 800ms ease-out',
        'tick-down': 'tick-down 800ms ease-out',
        'row-flash': 'row-flash 900ms ease-out',
      },
    },
  },
  plugins: [animate],
}

export default config
