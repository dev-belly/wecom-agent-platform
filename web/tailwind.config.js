/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#f4f6fa',
        surface: '#ffffff',
        surface2: '#ecf0f7',
        line: '#dbe2ec',
        muted: '#526178',
        fg: '#192336',
        teal: '#087468',
        blue: '#005fd9',
        violet: '#6743ad',
        amber: '#8a500b',
        rose: '#b52748',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
