module.exports = {
  content: ["./templates/**/*.html",
  "./static/**/*.js"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'neumorphic': '20px 20px 60px #d1d1d1, -20px -20px 60px #ffffff',
      }
    },
  },
  plugins: [],
}
