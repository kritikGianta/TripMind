import { apiFetch, type Schemas } from "@/lib/api/client";

export type User = Schemas["UserOut"];
export type Session = Schemas["SessionOut"];
export type RegisterInput = Schemas["RegisterRequest"];
export type LoginInput = Schemas["LoginRequest"];
export type DemoRole = NonNullable<Schemas["DemoLoginRequest"]["role"]>;

export const authApi = {
  me: (signal?: AbortSignal) => apiFetch<User>("/auth/me", { signal }),
  login: (body: LoginInput) => apiFetch<Session>("/auth/login", { method: "POST", body }),
  register: (body: RegisterInput) => apiFetch<Session>("/auth/register", { method: "POST", body }),
  demoLogin: (role: DemoRole) => apiFetch<Session>("/auth/demo-login", { method: "POST", body: { role } }),
  logout: () => apiFetch<void>("/auth/logout", { method: "POST" }),
};
