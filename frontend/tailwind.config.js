/** @type {import('tailwindcss').Config} */
export default {
    content: ['./index.html', './src/**/*.{js,jsx}'],
    theme: {
      extend: {
        fontFamily: {
          display: ['Syne', 'sans-serif'],
          body: ['DM Sans', 'sans-serif'],
          mono: ['"JetBrains Mono"', 'monospace'],
        },
        colors: {
          void:    '#060912',
          deep:    '#0a0f1e',
          surface: '#0e1526',
          panel:   '#121d30',
          border:  '#1a2540',
          muted:   '#273350',
          accent:  '#3b82f6',
          cyan:    '#06b6d4',
          glow:    '#60a5fa',
        },
        animation: {
          'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
          'fade-in':    'fadeIn 0.3s ease-out',
          'slide-up':   'slideUp 0.3s ease-out',
          'blink':      'blink 1s step-end infinite',
        },
        keyframes: {
          fadeIn:  { from: { opacity: 0 }, to: { opacity: 1 } },
          slideUp: { from: { opacity: 0, transform: 'translateY(12px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
          blink:   { '0%,100%': { opacity: 1 }, '50%': { opacity: 0 } },
        },
      },
    },
    plugins: [],
  }