/** @type {import('next').NextConfig} */
const path = require('path');

// Load environment variables from root .env file
require('dotenv').config({ 
  path: path.resolve(__dirname, '..', '.env') 
});

const nextConfig = {
  pageExtensions: ['ts', 'tsx'],
  experimental: {
    typedRoutes: true,
  },
  env: {
    // Expose specific environment variables to the client
    NEXT_PUBLIC_WEBSOCKET_URL: process.env.NEXT_PUBLIC_WEBSOCKET_URL,
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL,
    NEXT_PUBLIC_GEMINI_API_KEY: process.env.NEXT_PUBLIC_GEMINI_API_KEY,
  },
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
    };
    return config;
  },
}

module.exports = nextConfig