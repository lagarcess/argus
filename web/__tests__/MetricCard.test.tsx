import { describe, it, expect, afterEach } from "bun:test";
import { render, screen, cleanup } from "@testing-library/react";
import { MetricCard } from "../components/MetricCard";
import React from "react";

describe("MetricCard", () => {
  afterEach(() => {
    cleanup();
  });

  it("should render the value and label correctly", () => {
    render(<MetricCard value="14.2B" label="Strategies Tested" />);

    expect(screen.getByText("14.2B")).toBeTruthy();
    expect(screen.getByText("Strategies Tested")).toBeTruthy();
  });

  it("should apply custom className", () => {
    const { container } = render(
      <MetricCard value="0.1ms" label="Simulation Latency" className="custom-class" />
    );

    expect(container.firstChild).toHaveClass("custom-class");
  });
});
