/** @type {import('jest').Config} */
const baseConfig = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
  },
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {
      tsconfig: 'tsconfig.json',
    }],
  },
};

const config = {
  // Separate test suites
  projects: [
    {
      ...baseConfig,
      displayName: 'unit',
      testMatch: ['<rootDir>/lib/__tests__/**/*.test.ts'],
    },
    {
      ...baseConfig,
      displayName: 'analytics',
      testMatch: ['<rootDir>/tests/analytics/**/*.test.ts'],
      setupFilesAfterEnv: ['<rootDir>/tests/analytics/setup.ts'],
    },
  ],
  collectCoverageFrom: [
    'lib/**/*.ts',
    'app/api/**/*.ts',
    '!lib/**/__tests__/**',
    '!**/tests/**',
  ],
  // Default timeout for tests
  testTimeout: 10000,
  // Force exit to handle open handles from rate limiting tests
  forceExit: true,
};

module.exports = config;
