
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  type Ref,
} from 'react';
import { createPortal } from 'react-dom';

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

function focusableWithin(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter(
    (element) =>
      !element.hasAttribute('hidden') &&
      !element.hasAttribute('inert') &&
      element.getAttribute('aria-hidden') !== 'true' &&
      element.style.display !== 'none' &&
      element.style.visibility !== 'hidden',
  );
}

function hideBackground(except: HTMLElement): () => void {
  const changed: Array<{
    element: HTMLElement;
    ariaHidden: string | null;
    inert: string | null;
  }> = [];

  for (const child of Array.from(document.body.children)) {
    if (!(child instanceof HTMLElement) || child === except) continue;

    changed.push({
      element: child,
      ariaHidden: child.getAttribute('aria-hidden'),
      inert: child.getAttribute('inert'),
    });

    child.setAttribute('aria-hidden', 'true');
    child.setAttribute('inert', '');
  }

  return () => {
    for (const { element, ariaHidden, inert } of changed) {
      if (ariaHidden === null) element.removeAttribute('aria-hidden');
      else element.setAttribute('aria-hidden', ariaHidden);

      if (inert === null) element.removeAttribute('inert');
      else element.setAttribute('inert', inert);
    }
  };
}

function lockScroll(): () => void {
  const previous = document.body.style.overflow;
  document.body.style.overflow = 'hidden';
  return () => {
    document.body.style.overflow = previous;
  };
}

export interface ModalProps {
  
  open: boolean;
  
  onClose: () => void;
  
  title: ReactNode;
  children: ReactNode;
  
  panelClassName?: string;
  
  onSubmit?: (event: FormEvent<HTMLFormElement>) => void;
}

export function Modal({
  open,
  onClose,
  title,
  children,
  panelClassName,
  onSubmit,
}: ModalProps) {
  const panelRef = useRef<HTMLElement | null>(null);
  const titleId = useId();

  const openerRef = useRef<Element | null>(null);

  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;

    openerRef.current = document.activeElement;

    const panel = panelRef.current;
    
    panel?.focus();

    const releaseScroll = lockScroll();
    const revealBackground = panel?.parentElement
      ? hideBackground(panel.parentElement)
      : () => {};

    return () => {
      revealBackground();
      releaseScroll();

      const opener = openerRef.current;
      if (opener instanceof HTMLElement && document.contains(opener)) {
        opener.focus();
      }
    };
  }, [open]);

  const handleKeyDown = useCallback((event: ReactKeyboardEvent) => {
    if (event.key === 'Escape') {
      
      event.stopPropagation();
      onCloseRef.current();
      return;
    }

    if (event.key !== 'Tab') return;

    const panel = panelRef.current;
    if (!panel) return;

    const focusable = focusableWithin(panel);
    if (focusable.length === 0) {
      
      event.preventDefault();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;

    if (event.shiftKey) {
      
      if (active === first || active === panel || !panel.contains(active)) {
        event.preventDefault();
        last.focus();
      }
      return;
    }

    if (active === last) {
      event.preventDefault();
      first.focus();
    }
  }, []);

  if (!open) return null;

  const panelProps = {
    className: panelClassName,
    role: 'dialog',
    'aria-modal': true,
    'aria-labelledby': titleId,
    tabIndex: -1,
    onKeyDown: handleKeyDown,
  } as const;

  const heading = (
    <h2 id={titleId} className="modal-title">
      {title}
    </h2>
  );

  return createPortal(
    <div
      className="modal-backdrop"
      
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      {onSubmit ? (
        <form
          {...panelProps}
          ref={panelRef as Ref<HTMLFormElement>}
          onSubmit={onSubmit}
        >
          {heading}
          {children}
        </form>
      ) : (
        <div {...panelProps} ref={panelRef as Ref<HTMLDivElement>}>
          {heading}
          {children}
        </div>
      )}
    </div>,
    document.body,
  );
}
