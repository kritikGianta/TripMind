"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api/errors";

import { authApi, type DemoRole, type LoginInput, type RegisterInput, type Session, type User } from "./api";

export const sessionKey = ["auth", "session"] as const;

/**
 * The signed-in user, or `null` when signed out. A 401 is an answer ("signed out"), not an error.
 */
export function useSession() {
  const query = useQuery<User | null>({
    queryKey: sessionKey,
    queryFn: async ({ signal }) => {
      try {
        return await authApi.me(signal);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 60_000,
    retry: false,
  });
  return {
    user: query.data ?? null,
    status: query.isPending ? "loading" : query.data ? "authenticated" : "unauthenticated",
    error: query.error,
  } as const;
}

function useSessionMutation<TInput>(mutationFn: (input: TInput) => Promise<Session>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (session) => {
      queryClient.setQueryData(sessionKey, session.user);
    },
  });
}

export const useSignIn = () => useSessionMutation((input: LoginInput) => authApi.login(input));
export const useSignUp = () => useSessionMutation((input: RegisterInput) => authApi.register(input));
export const useDemoSignIn = () => useSessionMutation((role: DemoRole) => authApi.demoLogin(role));

export function useSignOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => authApi.logout(),
    onSettled: () => {
      // Signed-out state must never show cached private data.
      queryClient.clear();
      queryClient.setQueryData(sessionKey, null);
    },
  });
}
