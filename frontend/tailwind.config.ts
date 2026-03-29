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
      },
    },
  },
} satisfies Config
