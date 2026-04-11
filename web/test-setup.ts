import { GlobalRegistrator } from '@happy-dom/global-registrator';
import { expect } from 'bun:test';
import * as matchers from '@testing-library/jest-dom/matchers';

GlobalRegistrator.register();

// Extend bun:test with jest-dom matchers
expect.extend(matchers);
