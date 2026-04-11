import { describe, it, expect, mock, afterEach } from "bun:test";
import { render, screen, cleanup } from "@testing-library/react";
import { SparklinePreview } from "../components/SparklinePreview";
import React from "react";

// Recharts ResponsiveContainer needs to be mocked otherwise it fails to render in JSDOM/HappyDOM
mock.module("recharts", () => {
  return {
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
    LineChart: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="line-chart">{children}</div>
    ),
    Line: () => <div data-testid="line" />
  };
});

describe("SparklinePreview", () => {
  afterEach(() => {
    cleanup();
  });

  it("should render nothing when assetName is empty", () => {
    const { container } = render(<SparklinePreview assetName="" />);
    expect(container.firstChild).toBeNull();
  });

  it("should render the sparkline when assetName is provided", () => {
    render(<SparklinePreview assetName="BTC/USD" />);

    // Check if the mock container is rendered
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
    expect(screen.getByTestId("line-chart")).toBeInTheDocument();
    expect(screen.getByTestId("line")).toBeInTheDocument();
  });

  it("should render the sparkline for stablecoins", () => {
    render(<SparklinePreview assetName="USDT" />);

    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });
});
