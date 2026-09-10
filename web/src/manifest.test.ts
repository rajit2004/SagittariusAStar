import { describe, expect, it } from 'vitest';

import manifestRaw from '../public/manifest.webmanifest?raw';
import indexHtml from '../index.html?raw';
import icon192 from '../public/icon-192.svg?raw';
import icon512 from '../public/icon-512.svg?raw';

const ICON_SOURCES: Record<string, string> = {
  '/icon-192.svg': icon192,
  '/icon-512.svg': icon512,
};

describe('web app manifest', () => {
  it('is valid JSON', () => {
    expect(() => JSON.parse(manifestRaw)).not.toThrow();
  });

  const manifest = JSON.parse(manifestRaw);

  it('carries the fields a launcher needs to install it', () => {
    expect(manifest.name).toBeTruthy();
    expect(manifest.short_name).toBeTruthy();
    expect(manifest.start_url).toBe('/');
    expect(manifest.display).toBe('standalone');
    expect(manifest.theme_color).toBeTruthy();
    expect(manifest.background_color).toBeTruthy();
  });

  it('keeps short_name short enough not to be truncated under an icon', () => {
    expect(manifest.short_name.length).toBeLessThanOrEqual(12);
  });

  it('declares a maskable icon', () => {
    
    const maskable = (manifest.icons as { purpose?: string }[]).filter((icon) =>
      icon.purpose?.split(' ').includes('maskable'),
    );
    expect(maskable.length).toBeGreaterThan(0);
  });

  it('declares both a 192 and a 512 icon', () => {
    const sizes = (manifest.icons as { sizes: string }[]).map((icon) => icon.sizes);
    expect(sizes).toContain('192x192');
    expect(sizes).toContain('512x512');
  });

  it('points every icon at a file that exists and is not empty', () => {
    
    for (const icon of manifest.icons as { src: string }[]) {
      const source = ICON_SOURCES[icon.src];
      expect(source, `${icon.src} is not a known asset`).toBeDefined();
      expect(source.length, `${icon.src} is empty`).toBeGreaterThan(0);
      expect(source, `${icon.src} is not an SVG`).toContain('<svg');
    }
  });

  it('points every shortcut at a route the app serves', () => {
    const routes = [
      '/',
      '/cycle',
      '/assistant',
      '/insights',
      '/profile',
      '/settings',
      '/sharing',
      '/sms',
    ];
    for (const shortcut of (manifest.shortcuts ?? []) as { url: string }[]) {
      expect(routes, `${shortcut.url} is not a route`).toContain(shortcut.url);
    }
  });

  it('agrees with the theme-color in index.html', () => {
    expect(indexHtml).toContain(manifest.theme_color);
  });
});

describe('index.html', () => {
  it('no longer carries the Vite scaffold title', () => {
    expect(indexHtml).not.toMatch(/<title>web<\/title>/);
  });

  it('has a real title and description for a crawler that runs no JavaScript', () => {
    expect(indexHtml).toMatch(/<title>[^<]{10,}<\/title>/);
    expect(indexHtml).toMatch(/<meta\s+name="description"/);
  });

  it('links the manifest', () => {
    expect(indexHtml).toMatch(/rel="manifest"/);
  });

  it('carries Open Graph tags so a shared link previews', () => {
    for (const property of ['og:type', 'og:title', 'og:description', 'og:image']) {
      expect(indexHtml, `${property} missing`).toContain(property);
    }
  });

  it('does not leak the full path in a referrer', () => {
    
    expect(indexHtml).toMatch(/name="referrer"\s+content="strict-origin/);
  });
});
