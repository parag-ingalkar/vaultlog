import type { UseQueryResult } from "@tanstack/react-query";
import { isApiError } from "@/lib/api/errors";

export type QueryStateView = {
  isInitialLoading: boolean;
  isBackgroundFetching: boolean;
  isStale: boolean;
  isError: boolean;
  isEmpty: boolean;
  isRateLimited: boolean;
  retryAfter?: number;
  error: Error | null;
};

export function getQueryState<T>(
  query: Pick<
    UseQueryResult<T>,
    | "isPending"
    | "isFetching"
    | "isStale"
    | "isError"
    | "isSuccess"
    | "data"
    | "error"
  >,
  isEmpty?: (data: T | undefined) => boolean,
): QueryStateView {
  const error = query.error instanceof Error ? query.error : null;
  const rateLimited = isApiError(error) && error.isRateLimited();

  return {
    isInitialLoading: query.isPending && query.data === undefined,
    isBackgroundFetching: query.isFetching && !query.isPending,
    isStale: query.isStale,
    isError: query.isError,
    isEmpty:
      query.isSuccess &&
      (isEmpty
        ? isEmpty(query.data)
        : Array.isArray(query.data) && query.data.length === 0),
    isRateLimited: rateLimited,
    retryAfter: rateLimited && isApiError(error) ? error.retryAfter : undefined,
    error,
  };
}
