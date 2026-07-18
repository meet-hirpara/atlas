/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        claude: {
          bg: '#212121',
          sidebar: '#171717',
          surface: '#2f2f2f',
          elevated: '#383838',
          border: '#424242',
          text: '#ececec',
          muted: '#9b9b9b',
          accent: '#d97757',
          'accent-hover': '#e88b6b',
        },
      },
    },
  },
  plugins: [],
}
