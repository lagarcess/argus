export interface ApiErrorDetails {
  message: string;
  status?: number;
  code?: string;
  originalError?: unknown;
}

export function normalizeApiError(error: unknown): ApiErrorDetails {
  if (typeof error === 'object' && error !== null) {
    const err = error as Record<string, unknown>;

    // Check if it's our SDK error object structure (it typically wraps fetch errors or returns the body)
    if (err.error !== undefined && err.error !== null) {
       // err.error could be a string or an object with details
       if (typeof err.error === 'string') {
         return { message: err.error, status: err.status as number | undefined, originalError: error };
       }

       const errBody = err.error as Record<string, unknown>;

       if (typeof errBody.detail === 'string') {
         return { message: errBody.detail, status: err.status as number | undefined, originalError: error };
       } else if (typeof errBody.message === 'string') {
         return { message: errBody.message, status: err.status as number | undefined, code: errBody.code as string | undefined, originalError: error };
       }
    }

    // Handle standard JS errors
    if (typeof err.message === 'string') {
      return { message: err.message, status: (err.status as number | undefined) || 500, originalError: error };
    }
  }

  // Fallback
  return {
    message: typeof error === 'string' ? error : 'An unexpected error occurred.',
    originalError: error,
  };
}
