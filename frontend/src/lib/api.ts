export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      credentials: "include",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "DentFlow",
        ...options.headers,
      },
    });
  } catch {
    throw new ApiError(
      0,
      "Не удалось связаться с сервером. Проверьте подключение и повторите попытку.",
    );
  }
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("json") ? await response.json() : null;
  if (!response.ok) {
    let message =
      data?.detail || data?.message || "Не удалось выполнить действие.";
    if (Array.isArray(message))
      message = message
        .map(
          (e: { loc?: string[]; msg?: string }) =>
            `${e.loc?.slice(1).join(".") || "Поле"}: ${e.msg || "неверное значение"}`,
        )
        .join("; ");
    if (message && typeof message === "object" && Array.isArray(message.errors))
      message = `${message.message || "Проверьте поля"}: ${message.errors.map((e: { message?: string }) => e.message || "некорректное значение").join("; ")}`;
    if (typeof message !== "string")
      message = "Проверьте данные формы и повторите попытку.";
    throw new ApiError(response.status, message);
  }
  return data as T;
}

export function post<T>(path: string, body: unknown = {}) {
  return api<T>(path, { method: "POST", body: JSON.stringify(body) });
}
export function patch<T>(path: string, body: unknown) {
  return api<T>(path, { method: "PATCH", body: JSON.stringify(body) });
}
export function errorText(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Произошла ошибка. Повторите попытку.";
}
