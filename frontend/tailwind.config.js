/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f5ff',
          100: '#e0ecff',
          200: '#c7dcfe',
          300: '#a1c4fd',
          400: '#72a0fa',
          500: '#437af5',
          600: '#2359ea',
          700: '#1a43d6',
          800: '#1938ac',
          900: '#0f246b',
          950: '#0a1645',
        },
      },
    },
  },
  plugins: [],
}
