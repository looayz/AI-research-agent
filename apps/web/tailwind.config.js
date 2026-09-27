/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#0c0d0e',
        offwhite: '#f5f5f3',
        foreground: '#111213',
        card: {
          DEFAULT: '#ffffff',
          foreground: '#111213',
          border: '#e4e4e0',
        },
        sidebar: {
          DEFAULT: '#090a0b',
          border: '#1b1d20',
          text: '#9ba1a6',
        },
        primary: {
          DEFAULT: '#111213',
          foreground: '#ffffff',
          hover: '#27292d',
        },
        muted: {
          DEFAULT: '#eeeee9',
          foreground: '#6c7075',
        },
        border: '#e4e4e0',
      },
    },
  },
  plugins: [],
}
