import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#FFFFFF',
        surface: '#F3F3F3',
        ink: '#191A23',
        'ink-soft': '#4A4B57',
        accent: '#B9FF66',
        'accent-soft': '#E8FFD4',
        border: '#191A23',
        success: '#22C55E',
        warning: '#F59E0B',
        danger: '#EF4444',
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'system-ui', 'sans-serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        card: '16px',
        'card-lg': '24px',
      },
      boxShadow: {
        card: '0 2px 0 0 #191A23',
        'card-hover': '0 6px 0 0 #191A23',
      },
    },
  },
  plugins: [],
};

export default config;
