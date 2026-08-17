/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0d1117',
        surface: '#161b22',
        surface2: '#1c2128',
        line: '#30363d',
        muted: '#8b949e',
        fg: '#e6edf3',
        teal: '#2dd4bf',
        blue: '#3b82f6',
        violet: '#a78bfa',
        amber: '#fbbf24',
        rose: '#fb7185',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
