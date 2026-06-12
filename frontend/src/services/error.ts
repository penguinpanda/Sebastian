export function mapApiErrorMessage(params: {
  status?: number;
  errorCode?: string | null;
  detail?: string | null;
  fallback?: string;
}): string {
  const { status, errorCode, detail, fallback = '请求失败，请稍后重试' } = params;

  if (detail && detail.trim()) {
    return detail;
  }

  if (errorCode === 'VALIDATION_ERROR' || status === 400 || status === 422) {
    return '请求参数不合法，请检查输入';
  }

  if (errorCode === 'BUSINESS_ERROR' || status === 409) {
    return '业务冲突，请调整后重试';
  }

  if (errorCode === 'RETRYABLE_ERROR' || status === 503) {
    return '服务暂时不可用，请稍后重试';
  }

  if (status === 429) {
    return '请求过于频繁，请稍后再试';
  }

  if (errorCode === 'FATAL_ERROR' || status === 500) {
    return '系统内部错误，请稍后重试';
  }

  return fallback;
}

export function getFriendlyError(error: unknown, fallback?: string): string {
  const maybeError = error as {
    friendlyMessage?: string;
    response?: {
      status?: number;
      data?: {
        detail?: string;
        error_code?: string;
        error_message?: string;
      };
    };
    message?: string;
  };

  if (maybeError?.friendlyMessage) {
    return maybeError.friendlyMessage;
  }

  const status = maybeError?.response?.status;
  const detail = maybeError?.response?.data?.detail || maybeError?.response?.data?.error_message;
  const errorCode = maybeError?.response?.data?.error_code;

  return mapApiErrorMessage({
    status,
    errorCode,
    detail,
    fallback: fallback || maybeError?.message || '请求失败，请稍后重试',
  });
}
