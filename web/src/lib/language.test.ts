import { describe, expect, it } from 'vitest';

import {
  ASSISTANT_LANGUAGES,
  isAssistantLanguageFallback,
  toAssistantLanguage,
} from './language';

describe('toAssistantLanguage', () => {
  it.each(ASSISTANT_LANGUAGES)('passes the supported code %s through', (code) => {
    expect(toAssistantLanguage(code)).toBe(code);
  });

  it.each([
    ['en-US', 'en'],
    ['en-GB', 'en'],
    ['hi-IN', 'hi'],
    ['ta-IN', 'ta'],
  ])('reduces the region tag %s to %s', (input, expected) => {
    
    expect(toAssistantLanguage(input)).toBe(expected);
  });

  it('handles underscore-separated tags', () => {
    expect(toAssistantLanguage('hi_IN')).toBe('hi');
  });

  it('is case-insensitive', () => {
    expect(toAssistantLanguage('HI')).toBe('hi');
    expect(toAssistantLanguage('EN-us')).toBe('en');
  });

  it('falls back to English for a language the assistant does not speak', () => {
    
    expect(toAssistantLanguage('bn')).toBe('en');
  });

  it('falls back to English for anything unrecognized', () => {
    expect(toAssistantLanguage('klingon')).toBe('en');
    expect(toAssistantLanguage('')).toBe('en');
    expect(toAssistantLanguage(undefined)).toBe('en');
    expect(toAssistantLanguage('   ')).toBe('en');
  });
});

describe('isAssistantLanguageFallback', () => {
  it('is true when the UI language is not one the assistant speaks', () => {
    expect(isAssistantLanguageFallback('bn')).toBe(true);
  });

  it('is false for a supported language, with or without a region tag', () => {
    expect(isAssistantLanguageFallback('hi')).toBe(false);
    expect(isAssistantLanguageFallback('hi-IN')).toBe(false);
  });

  it('is false for English, which is not a fallback but a choice', () => {
    expect(isAssistantLanguageFallback('en')).toBe(false);
    expect(isAssistantLanguageFallback('en-US')).toBe(false);
  });

  it('is false when there is no UI language to judge', () => {
    expect(isAssistantLanguageFallback(undefined)).toBe(false);
  });
});
