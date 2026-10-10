import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error caught by ErrorBoundary:', error, errorInfo);
  }

  public handleReload = () => {
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div style={{
          height: '100vh',
          width: '100vw',
          background: '#070a13',
          color: '#e2e8f0',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
        }}>
          <div style={{
            background: 'rgba(15, 23, 42, 0.95)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: '12px',
            padding: '28px',
            maxWidth: '520px',
            textAlign: 'center',
            boxShadow: '0 12px 40px rgba(0,0,0,0.8)'
          }}>
            <h2 style={{ color: '#ef4444', marginBottom: '12px', fontSize: '1.25rem' }}>
              ⚠️ Dashboard Exception Intercepted
            </h2>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8', lineHeight: '1.6', marginBottom: '20px' }}>
              The diagnostic interface encountered a transient rendering exception. State telemetry remains active in the background.
            </p>
            <div style={{
              background: '#020617',
              padding: '10px 14px',
              borderRadius: '6px',
              fontSize: '0.75rem',
              color: '#f87171',
              fontFamily: 'monospace',
              textAlign: 'left',
              marginBottom: '20px',
              overflowX: 'auto'
            }}>
              {this.state.error?.message || 'Unknown render error'}
            </div>
            <button
              onClick={this.handleReload}
              style={{
                background: '#0284c7',
                color: '#ffffff',
                border: 'none',
                padding: '10px 20px',
                borderRadius: '6px',
                fontWeight: 600,
                fontSize: '0.85rem',
                cursor: 'pointer'
              }}
            >
              🔄 Reload Dashboard
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
