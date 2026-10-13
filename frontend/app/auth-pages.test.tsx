import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api-error";
import LoginPage from "./login/page";
import RegisterPage from "./register/page";

const { loginMock, registerMock, pushMock } = vi.hoisted(() => ({
  loginMock: vi.fn(),
  registerMock: vi.fn(),
  pushMock: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({ login: loginMock, registerAccount: registerMock }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: pushMock }) }));

beforeEach(() => {
  loginMock.mockReset();
  registerMock.mockReset();
  pushMock.mockReset();
});

describe("LoginPage", () => {
  it("shows Spanish labels", () => {
    render(<LoginPage />);
    expect(screen.getByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Iniciar sesión" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Regístrate" })).toBeInTheDocument();
  });

  it("shows Spanish text for invalid_credentials, not the English detail", async () => {
    loginMock.mockRejectedValue(new ApiError({ detail: "bad creds", code: "invalid_credentials" }));
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.type(screen.getByLabelText("Email"), "a@b.co");
    await user.type(screen.getByLabelText("Contraseña"), "x");
    await user.click(screen.getByRole("button", { name: "Iniciar sesión" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Email o contraseña incorrectos.");
    expect(screen.queryByText("bad creds")).not.toBeInTheDocument();
  });
});

describe("RegisterPage", () => {
  it("shows Spanish labels", () => {
    render(<RegisterPage />);
    expect(screen.getByRole("heading", { name: "Crear cuenta" })).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Crear cuenta" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Inicia sesión" })).toBeInTheDocument();
  });

  it("shows Spanish text for duplicate_email, not the English detail", async () => {
    registerMock.mockRejectedValue(
      new ApiError({ detail: "Email already registered", code: "duplicate_email" }),
    );
    const user = userEvent.setup();
    render(<RegisterPage />);
    await user.type(screen.getByLabelText("Email"), "a@b.co");
    await user.type(screen.getByLabelText("Contraseña"), "long-enough-pass");
    await user.click(screen.getByRole("button", { name: "Crear cuenta" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ya existe una cuenta con ese email.",
    );
    expect(screen.queryByText("Email already registered")).not.toBeInTheDocument();
  });

  it("shows the generic Spanish message for an unknown code", async () => {
    registerMock.mockRejectedValue(new ApiError({ detail: "Boom", code: "brand_new_code" }));
    const user = userEvent.setup();
    render(<RegisterPage />);
    await user.type(screen.getByLabelText("Email"), "a@b.co");
    await user.type(screen.getByLabelText("Contraseña"), "long-enough-pass");
    await user.click(screen.getByRole("button", { name: "Crear cuenta" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Algo salió mal. Inténtalo de nuevo."),
    );
    expect(pushMock).not.toHaveBeenCalled();
  });
});
