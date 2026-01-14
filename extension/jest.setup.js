// Jest setup file for frontend tests

// Mock chrome APIs
global.chrome = {
  storage: {
    local: {
      get: jest.fn(),
      set: jest.fn(),
    },
  },
  runtime: {
    onInstalled: {
      addListener: jest.fn(),
    },
  },
};

// Mock fetch
global.fetch = jest.fn();

// Polyfill crypto.randomUUID for Jest (jsdom) environments where it may be missing
if (!global.crypto) {
  global.crypto = {};
}
if (typeof global.crypto.randomUUID !== 'function') {
  let __uuidCounter = 0;
  global.crypto.randomUUID = () => `test-uuid-${++__uuidCounter}`;
}
