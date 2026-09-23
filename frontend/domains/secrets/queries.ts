import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { listSecrets } from "./api";

export function useSecretsQuery(vaultId: string) {
  return useQuery({
    queryKey: queryKeys.secrets.list(vaultId),
    queryFn: () => listSecrets(vaultId),
    enabled: Boolean(vaultId),
  });
}
