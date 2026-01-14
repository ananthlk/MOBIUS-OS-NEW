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
