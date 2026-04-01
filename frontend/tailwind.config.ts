import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        tribal: {
          bg: '#0d0d14',
          panel: '#1a1a2e',
          card: '#16213e',
          border: '#2d2d4e',
          muted: '#3d3d5e',
        },
        // Accent palette — derived from user brand colors:
        //   blue #233775 · purple #623B75 · green #50753B
        // Each has three levels:
        //   DEFAULT = mid-brightness, readable as text on dark backgrounds
        //   dark    = the base brand color, used for button fills and badge backgrounds
        //   light   = lighter variant for hover/secondary text states
        accent: {
          blue: {
            DEFAULT: '#4a78c2',
            dark: '#233775',
            light: '#7aa0d4',
          },
          purple: {
            DEFAULT: '#8a52a0',
            dark: '#623B75',
            light: '#b07bc4',
          },
          green: {
            DEFAULT: '#6a9e4a',
            dark: '#50753B',
            light: '#8fbf6a',
          },
          gray: '#7a7a8c',
        },
        // Urgency status colors — same traffic-light semantics as before but
        // desaturated and pulled toward the earthy blue-green palette.
        // DEFAULT is mid-brightness (text/icons on dark bg); bg/border use opacity modifiers.
        status: {
          overdue:  '#e06868', // dusty rose-red  (was: electric red-400)
          critical: '#e0924a', // burnt sienna     (was: neon orange-400)
          warning:  '#d4aa20', // golden amber     (was: bright amber-400)
          upcoming: '#c8b83a', // muted olive-gold (was: electric yellow-400)
        },
        // Danger red — for destructive UI actions (delete buttons, error states, sign out)
        danger: {
          DEFAULT: '#d95555', // muted red for text/icons
          dark:    '#9e2424', // for button fills
          light:   '#e87070', // for hover states
        },
      },
    },
  },
} satisfies Config
