import { describe, it, expect } from 'vitest';
import kn from '../locales/kn.json';
import ml from '../locales/ml.json';

describe('Kannada and Malayalam Locale QA & Rendering Checks', () => {
  it('loads Kannada locale without crashing', () => {
    expect(kn).toBeDefined();
    expect(typeof kn).toBe('object');
  });

  it('loads Malayalam locale without crashing', () => {
    expect(ml).toBeDefined();
    expect(typeof ml).toBe('object');
  });

  it('Kannada has at least a partial translation', () => {
    const keys = Object.keys(kn);
    expect(keys.length).toBeGreaterThan(5);
  });

  it('Malayalam has at least a partial translation', () => {
    const keys = Object.keys(ml);
    expect(keys.length).toBeGreaterThan(5);
  });
});
