module.exports = {
  content: ["./src/eltariff/templates/**/*.html"],
  theme: {
    extend: {
      colors: {
        sourceful: {
          grey: "#2B2B2B",
          blue: "#2F4A66",
          green: "#017E7A",
          teal: "#00FF84"
        }
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"]
      }
    }
  },
  plugins: []
};
