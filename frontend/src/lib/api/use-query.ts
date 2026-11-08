"use client";

import { useQuery as useTanstackQuery, type UseQueryResult } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

/** False while React hydrates this component from server HTML, true from then on and on client navigation. */
function useHydrated() {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
}

/**
 * TanStack's useQuery, safe to hydrate. Always import this one (a lint rule enforces it).
 *
 * The server has no query cache, so its HTML always shows the loading state. A Suspense boundary can
 * hydrate after an earlier component's request has already finished; the raw hook would then render
 * that cached answer, React would see HTML that does not match (error #418), throw the boundary's
 * server HTML away and render it again, losing anything the visitor had typed there. So until this
 * component has hydrated, report what the server rendered; the answer follows immediately after.
 */
export const useQuery = ((...args: Parameters<typeof useTanstackQuery>) => {
  const hydrated = useHydrated();
  const result = useTanstackQuery(...args) as UseQueryResult;
  if (hydrated || result.status === "pending") return result;
  return {
    ...result,
    data: undefined,
    error: null,
    status: "pending",
    fetchStatus: "fetching",
    dataUpdatedAt: 0,
    isPending: true,
    isLoading: true,
    isInitialLoading: true,
    isFetching: true,
    isSuccess: false,
    isError: false,
    isLoadingError: false,
    isRefetchError: false,
    isRefetching: false,
    isFetched: false,
    isFetchedAfterMount: false,
    isPlaceholderData: false,
    isStale: true,
  };
}) as typeof useTanstackQuery;
