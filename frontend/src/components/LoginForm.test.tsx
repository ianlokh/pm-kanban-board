import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/components/LoginForm";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("LoginForm", () => {
  it("submits credentials and reports the signed-in user", async () => {
    const onLogin = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ username: "user" }),
      })
    );

    render(<LoginForm onLogin={onLogin} />);
    await userEvent.type(screen.getByLabelText("Username"), "user");
    await userEvent.type(screen.getByLabelText("Password"), "password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(onLogin).toHaveBeenCalledWith({ username: "user" });
  });

  it("shows the API error when credentials are rejected", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ detail: "Invalid username or password" }),
      })
    );

    render(<LoginForm onLogin={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("Username"), "user");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid username or password"
    );
  });
});
