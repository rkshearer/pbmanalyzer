import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  onReset?: () => void
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
    this.props.onReset?.()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="error-boundary-card">
            <div className="error-boundary-icon" aria-hidden="true">!</div>
            <h2 className="error-boundary-title">Something went wrong</h2>
            <p className="error-boundary-message">
              An unexpected error occurred. Please try again.
            </p>
            {this.state.error && (
              <details className="error-boundary-details">
                <summary>Technical details</summary>
                <code>{this.state.error.message}</code>
              </details>
            )}
            <button className="btn btn-primary" onClick={this.handleReset}>
              Start Over
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
