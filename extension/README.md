# Mobius OS Extension

AI-native, context-aware browser extension bridging financial and patient engagement with clinical care.

## Development

### Setup

```bash
npm install
```

### Build

```bash
npm run build
```

### Development (watch mode)

```bash
npm run dev
```

### Type Checking

```bash
npm run type-check
```

## Structure

```
extension/
├── src/
│   ├── components/        # Reusable UI components (27 components)
│   │   ├── header/       # Header components
│   │   ├── context/      # Context components
│   │   ├── tasks/        # Tasks components
│   │   ├── chat/         # Chat components
│   │   ├── feedback/     # Feedback components
│   │   ├── guidance/     # Guidance components
│   │   ├── input/        # Input components
│   │   ├── actions/      # Action components
│   │   ├── footer/       # Footer components
│   │   └── utils/        # Utility components
│   ├── services/         # API services
│   ├── types/            # TypeScript type definitions
│   ├── utils/            # Utility functions
│   ├── popup.ts          # Popup entry point
│   ├── background.ts     # Background service worker
│   └── content.ts        # Content script
├── public/               # Static assets
├── dist/                 # Build output
├── manifest.json         # Extension manifest
├── webpack.config.js     # Webpack configuration
├── tsconfig.json         # TypeScript configuration
└── package.json          # Dependencies
```

## Loading Extension

1. Build the extension: `npm run build`
2. Open Chrome and go to `chrome://extensions/`
3. Enable "Developer mode"
4. Click "Load unpacked"
5. Select the `extension/dist` directory
