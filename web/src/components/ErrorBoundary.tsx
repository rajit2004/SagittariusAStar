import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { getLastRequestId } from '../api/client';

interface Props {
  children: ReactNode;
  
  resetKey?: string;
  
  onError?: (error: Error, info: ErrorInfo) => void;
}

interface State {
  error: Error | null;
  requestId: string | null;
  
  seenResetKey: string | undefined;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, requestId: null, seenResetKey: this.props.resetKey };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    if (props.resetKey === state.seenResetKey) return null;

    return state.error
      ? { error: null, requestId: null, seenResetKey: props.resetKey }
      : { seenResetKey: props.resetKey };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    
    this.setState({ requestId: getLastRequestId() });

    console.error('Unhandled render error:', error, info.componentStack);

    this.props.onError?.(error, info);
  }

  reset = () => {
    this.setState({ error: null, requestId: null });
  };

  render() {
    if (this.state.error) {
      return <ErrorFallback requestId={this.state.requestId} onRetry={this.reset} />;
    }

    return this.props.children;
  }
}

function ErrorFallback({
  requestId,
  onRetry,
}: {
  requestId: string | null;
  onRetry: () => void;
}) {
  const { t } = useTranslation();

  return (
    <div className="page error-boundary" role="alert">
      <h1>{t('errors.boundaryTitle')}</h1>
      <p className="card-sub">{t('errors.boundaryBody')}</p>

      <div className="error-boundary-actions">
        {}
        <button type="button" className="primary-btn" onClick={onRetry}>
          {t('errors.retry')}
        </button>
        <Link className="ghost-btn" to="/">
          {t('errors.goHome')}
        </Link>
      </div>

      {requestId && (
        <p className="card-sub error-request-id">
          {t('errors.requestId')}: <code>{requestId}</code>
        </p>
      )}
    </div>
  );
}

export function RouteErrorBoundary({ children }: { children: ReactNode }) {
  const location = useLocation();

  return <ErrorBoundary resetKey={location.pathname}>{children}</ErrorBoundary>;
}
