/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./findshows/templates/findshows/*/*.html",
            "./templates/localmusic/*.html"],

  theme: {
    extend: {},
  },

  plugins: [],

  safelist: [
    'line-through',
  ],
}

