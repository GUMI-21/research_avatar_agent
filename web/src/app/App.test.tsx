import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("Agent workspace shell", () => {
  it("shows the auditable workspace panels", () => {
    render(<App />);

    expect(screen.getByText("Personal Agent")).toBeInTheDocument();
    expect(screen.getByText("检索上下文")).toBeInTheDocument();
    expect(screen.getByText("为什么选择 Agent")).toBeInTheDocument();
    expect(screen.getByText("本次运行")).toBeInTheDocument();
  });
});
