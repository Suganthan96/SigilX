"use client";

import React from "react";

interface CanvasErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface CanvasErrorBoundaryState {
  hasError: boolean;
}

export default class CanvasErrorBoundary extends React.Component<
  CanvasErrorBoundaryProps,
  CanvasErrorBoundaryState
> {
  constructor(props: CanvasErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    console.warn("WebGL canvas failed to initialize, falling back:", error);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? null;
    }
    return this.props.children;
  }
}
