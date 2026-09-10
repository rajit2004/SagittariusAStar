import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { I18nextProvider } from 'react-i18next';
import { MemoryRouter, Route, Routes, Link } from 'react-router-dom';

import i18n from '../../i18n';
import { MAIN_CONTENT_ID, SkipToContent } from '../SkipToContent';
import { RouteAnnouncer } from '../RouteAnnouncer';
import { routeTitleKey } from '../../lib/routeTitles';
import { ScrollToTopButton } from '../ScrollToTopButton';

function Harness({ initial = '/' }: { initial?: string }) {
  return (
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={[initial]}>
        <SkipToContent />
        <RouteAnnouncer />
        <nav aria-label="Main">
          <Link to="/">Home</Link>
          <Link to="/insights">Insights</Link>
        </nav>
        <main id={MAIN_CONTENT_ID} tabIndex={-1}>
          <Routes>
            <Route path="/" element={<h1>Home page</h1>} />
            <Route path="/insights" element={<h1>Insights page</h1>} />
          </Routes>
        </main>
      </MemoryRouter>
    </I18nextProvider>
  );
}

describe('skip to content', () => {
  it('is the first thing Tab reaches', async () => {
    
    const user = userEvent.setup();
    render(<Harness />);

    await user.tab();

    expect(document.activeElement).toHaveTextContent(/skip to content/i);
  });

  it('points at the main landmark', () => {
    render(<Harness />);

    const link = screen.getByRole('link', { name: /skip to content/i });
    expect(link).toHaveAttribute('href', `#${MAIN_CONTENT_ID}`);
    
    expect(document.getElementById(MAIN_CONTENT_ID)).not.toBeNull();
  });

  it('stays in the focus order while hidden', () => {
    
    render(<Harness />);

    const link = screen.getByRole('link', { name: /skip to content/i });
    expect(link).toBeVisible();
    expect(link).not.toHaveAttribute('hidden');
    expect(link).not.toHaveAttribute('aria-hidden');
  });

  it('is localized rather than hardcoded English', async () => {
    render(<Harness />);
    await i18n.changeLanguage('hi');

    await waitFor(() => {
      expect(
        screen.getByRole('link', { name: i18n.t('a11y.skipToContent') }),
      ).toBeInTheDocument();
    });

    await i18n.changeLanguage('en');
  });
});

describe('route announcer', () => {
  it('renders a polite live region', () => {
    render(<Harness />);

    const region = screen.getByRole('status');
    expect(region).toHaveAttribute('aria-live', 'polite');
    
    expect(region).toHaveAttribute('aria-atomic', 'true');
  });

  it('says nothing on the initial render', () => {
    
    render(<Harness />);

    expect(screen.getByRole('status')).toHaveTextContent('');
  });

  it('announces the new page after a navigation', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole('link', { name: 'Insights' }));

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/insights/i);
    });
  });

  it('does not steal focus on the initial render', () => {
    
    render(<Harness />);

    expect(document.activeElement).not.toBe(document.getElementById(MAIN_CONTENT_ID));
  });

  it('moves focus into main after a navigation', async () => {
    
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole('link', { name: 'Insights' }));

    await waitFor(() => {
      expect(document.activeElement).toBe(document.getElementById(MAIN_CONTENT_ID));
    });
  });

  it('leaves main out of the Tab order', async () => {
    render(<Harness />);

    expect(document.getElementById(MAIN_CONTENT_ID)).toHaveAttribute('tabindex', '-1');
  });
});

describe('routeTitleKey', () => {
  it.each([
    ['/', 'meta.home.title'],
    ['/cycle', 'meta.cycle.title'],
    ['/insights', 'meta.insights.title'],
    ['/sharing', 'meta.sharing.title'],
    ['/provider', 'meta.providerDashboard.title'],
  ])('%s maps to %s', (path, key) => {
    expect(routeTitleKey(path)).toBe(key);
  });

  it('prefers the more specific provider route', () => {
    
    expect(routeTitleKey('/provider/patients/abc')).toBe('meta.providerPatient.title');
    expect(routeTitleKey('/provider/login')).toBe('meta.providerLogin.title');
  });

  it('falls back to the app name for an unknown path', () => {
    
    expect(routeTitleKey('/nothing-here')).toBe('meta.appName');
  });
});

describe('scroll to top button', () => {
  function renderScrollButton() {
    return render(
      <I18nextProvider i18n={i18n}>
        <ScrollToTopButton />
      </I18nextProvider>,
    );
  }

  it('exposes a localized accessible name', async () => {
    
    renderScrollButton();
    Object.defineProperty(window, 'scrollY', { value: 500, configurable: true });
    window.dispatchEvent(new Event('scroll'));

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: i18n.t('a11y.scrollToTop') }),
      ).toBeInTheDocument();
    });
  });

  it('hides the arrow glyph from the accessibility tree', async () => {
    renderScrollButton();
    Object.defineProperty(window, 'scrollY', { value: 500, configurable: true });
    window.dispatchEvent(new Event('scroll'));

    await waitFor(() => {
      const button = screen.getByRole('button');
      
      expect(button.querySelector('[aria-hidden="true"]')).not.toBeNull();
    });
  });
});

describe('decorative cursor', () => {
  it('is hidden from the accessibility tree', async () => {
    
    const hadTouchStart = 'ontouchstart' in window;
    if (hadTouchStart) {
      delete (window as unknown as Record<string, unknown>).ontouchstart;
    }

    try {
      const { CustomCursor } = await import('../CustomCursor');
      const { container } = render(<CustomCursor />);

      const decorations = container.querySelectorAll('div');
      
      expect(decorations.length).toBeGreaterThan(0);

      for (const node of decorations) {
        
        expect(node).toHaveAttribute('aria-hidden', 'true');
      }
    } finally {
      if (hadTouchStart) {
        (window as unknown as Record<string, unknown>).ontouchstart = undefined;
      }
    }
  });
});
