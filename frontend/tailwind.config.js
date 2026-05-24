/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        trust: {
          DEFAULT: '#1B4F8A',
          dark: '#153D6B',
        },
        alert: {
          DEFAULT: '#D93B3B',
          soft: '#FEF2F2',
        },
        ok: {
          DEFAULT: '#15803D',
          soft: '#F0FDF4',
        },
        warn: {
          DEFAULT: '#D97706',
          soft: '#FFFBEB',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
