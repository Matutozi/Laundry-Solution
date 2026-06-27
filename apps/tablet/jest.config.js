module.exports = {
  testEnvironment: 'node',
  testMatch: ['**/__tests__/**/*.test.ts'],
  transform: {
    '^.+\\.(ts|tsx|js|jsx)$': [
      'babel-jest',
      { configFile: './babel.config.test.js' },
    ],
  },
  moduleNameMapper: {
    '@wise-wash/shared': '<rootDir>/../../packages/shared/src/index.ts',
  },
  // WatermelonDB uses ESM; allow jest to transform it
  transformIgnorePatterns: [
    'node_modules/(?!(@nozbe/watermelondb)/)',
  ],
}
