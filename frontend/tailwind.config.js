/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        surface: '#111111',
        card: 'rgba(255,255,255,0.04)',
        'card-border': 'rgba(255,255,255,0.06)',
        'accent-blue': '#2D9CFF',
        'accent-green': '#39D98A',
        'accent-orange': '#FF8A34',
        'accent-yellow': '#F2C94C',
        'accent-red': '#EB5757',
        'text-secondary': '#BDBDBD',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        glass: '20px',
      },
      backdropBlur: {
        glass: '20px',
      },
      animation: {
        'pulse-slow': 'pulse 2.5s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
