const path = require('path');
const webpack = require('webpack');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const CopyWebpackPlugin = require('copy-webpack-plugin');

module.exports = (env, argv) => {
  // Determine if this is a production build based on:
  // 1. BUILD_TARGET env var (build:prod vs build:dev scripts)
  // 2. Fallback to webpack mode
  const isProduction = env?.BUILD_TARGET === 'production' || argv.mode === 'production';
  
  console.log(`\n📦 Building for: ${isProduction ? 'PRODUCTION' : 'DEVELOPMENT'}`);
  console.log(`   API Target: ${isProduction ? 'https://mobius-os-backend-mc2ivyhdxq-uc.a.run.app' : 'http://localhost:5001'}\n`);

  return {
  entry: {
    popup: './src/popup.ts',
    background: './src/background.ts',
    content: './src/content.ts'
  },
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: '[name].js',
    clean: true
  },
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        use: 'ts-loader',
        exclude: /node_modules/
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader']
      }
    ]
  },
  resolve: {
    extensions: ['.ts', '.tsx', '.js'],
    alias: {
      '@components': path.resolve(__dirname, 'src/components'),
      '@services': path.resolve(__dirname, 'src/services'),
      '@types': path.resolve(__dirname, 'src/types'),
      '@utils': path.resolve(__dirname, 'src/utils')
    }
  },
  plugins: [
    // Inject PRODUCTION flag at build time
    new webpack.DefinePlugin({
      'process.env.PRODUCTION': JSON.stringify(isProduction),
    }),
    new HtmlWebpackPlugin({
      template: './src/popup.html',
      filename: 'popup.html',
      chunks: ['popup']
    }),
    new CopyWebpackPlugin({
      patterns: [
        { from: 'manifest.json', to: 'manifest.json' },
        { from: 'icons', to: 'icons', noErrorOnMissing: true }
      ]
    })
  ],
  devtool: isProduction ? false : 'source-map'
  };
};
