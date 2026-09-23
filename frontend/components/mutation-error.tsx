import { isApiError } from "@/lib/api/errors";

export function MutationError({ error }: { error: unknown }) {
  if (!error) return null;

  const message = isApiError(error)
    ? error.message
    : error instanceof Error
      ? error.message
      : "Something went wrong.";

  return (
    <p className="text-sm text-danger" role="alert">
      {message}
    </p>
  );
}
