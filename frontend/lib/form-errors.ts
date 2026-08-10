import type { ValidationField } from "@/lib/api/errors";

export function fieldErrorsFromApi(
  fields: ValidationField[] | undefined,
): Record<string, string> {
  if (!fields?.length) return {};

  const errors: Record<string, string> = {};
  for (const field of fields) {
    const key = String(field.loc[field.loc.length - 1] ?? "");
    if (key && !errors[key]) {
      errors[key] = field.type.replaceAll("_", " ");
    }
  }
  return errors;
}
