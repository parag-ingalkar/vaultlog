import type { QueryClient, QueryKey } from "@tanstack/react-query";

type OptimisticListUpdateOptions<T> = {
  queryClient: QueryClient;
  queryKey: QueryKey;
  updater: (current: T | undefined) => T | undefined;
  mutationFn: () => Promise<unknown>;
};

export async function optimisticListUpdate<T>({
  queryClient,
  queryKey,
  updater,
  mutationFn,
}: OptimisticListUpdateOptions<T>): Promise<void> {
  await queryClient.cancelQueries({ queryKey });
  const previous = queryClient.getQueryData<T>(queryKey);
  queryClient.setQueryData(queryKey, updater(previous));

  try {
    await mutationFn();
  } catch (error) {
    queryClient.setQueryData(queryKey, previous);
    throw error;
  } finally {
    queryClient.invalidateQueries({ queryKey });
  }
}
