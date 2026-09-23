export type ValidationField = {
  loc: (string | number)[];
  type: string;
};

export type ApiErrorBody = {
  code: string;
  message: string;
  request_id?: string | null;
  fields?: ValidationField[];
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId?: string | null;
  readonly fields?: ValidationField[];
  readonly retryAfter?: number;

  constructor(
    status: number,
    body: ApiErrorBody,
    retryAfter?: number,
  ) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.requestId = body.request_id;
    this.fields = body.fields;
    this.retryAfter = retryAfter;
  }

  isAuthError(): boolean {
    return this.status === 401;
  }

  isForbidden(): boolean {
    return this.status === 403;
  }

  isValidationError(): boolean {
    return this.status === 422 && this.code === "validation_failed";
  }

  isRateLimited(): boolean {
    return this.status === 429;
  }

  isStepUpRequired(): boolean {
    return this.status === 403 && this.code === "step_up_required";
  }

  isMfaEnrollmentRequired(): boolean {
    return this.status === 403 && this.code === "mfa_enrollment_required";
  }
}

export class StepUpRequiredError extends Error {
  readonly purpose: string;

  constructor(purpose: string) {
    super(`Step-up required for ${purpose}`);
    this.name = "StepUpRequiredError";
    this.purpose = purpose;
  }
}

type ErrorEnvelope = {
  error?: ApiErrorBody;
};

export async function parseApiError(
  response: Response,
): Promise<ApiError> {
  let body: ErrorEnvelope = {};
  try {
    body = (await response.json()) as ErrorEnvelope;
  } catch {
    // ignore parse failures
  }

  const retryAfterHeader = response.headers.get("Retry-After");
  const retryAfter = retryAfterHeader
    ? Number.parseInt(retryAfterHeader, 10)
    : undefined;

  const errorBody: ApiErrorBody = body.error ?? {
    code: `http_${response.status}`,
    message: response.statusText || "Request failed",
  };

  return new ApiError(response.status, errorBody, retryAfter);
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function isStepUpRequiredError(
  error: unknown,
): error is StepUpRequiredError {
  return error instanceof StepUpRequiredError;
}
