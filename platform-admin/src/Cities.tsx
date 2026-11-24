
import { useCallback, useEffect, useState, type FormEvent } from "react";

const API_BASE = "/api/v1/platform-admin";

type City = {
  id: string;
  name: string;
  code: string;
  is_active: boolean;
  created_at?: string;
};

type CitiesResponse = {
  items: City[];
  total: number;
};

type Props = {
  token: string;
  onBack?: () => void;
};

function getApiError(data: unknown): string {
  if (!data || typeof data !== "object") {
    return "Не удалось выполнить запрос";
  }

  const detail = (data as { detail?: unknown }).detail;

  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          return String(item.msg);
        }
        return String(item);
      })
      .join("; ");
  }

  return "Не удалось выполнить запрос";
}

function formatDate(value?: string): string {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleString("ru-RU");
}

export default function Cities({ token, onBack }: Props) {
  const [cities, setCities] = useState<City[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionId, setActionId] = useState("");

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [name, setName] = useState("");
  const [code, setCode] = useState("");

  const [editingId, setEditingId] = useState("");
  const [editName, setEditName] = useState("");
  const [editCode, setEditCode] = useState("");

  async function apiRequest<T>(
    path: string,
    options: RequestInit = {},
  ): Promise<T> {
    const headers = new Headers(options.headers);

    headers.set("Authorization", `Bearer ${token}`);

    if (options.body) {
      headers.set("Content-Type", "application/json");
    }

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      throw new Error(
        getApiError(data) || `Ошибка HTTP ${response.status}`,
      );
    }

    return data as T;
  }

  const loadCities = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const result = await apiRequest<CitiesResponse>("/cities");

      setCities(result.items || []);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Не удалось загрузить список городов",
      );
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void loadCities();
  }, [loadCities]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setSuccess("");

    const cleanName = name.trim();
    const cleanCode = code.trim().toLowerCase();

    if (cleanName.length < 2) {
      setError("Название города должно содержать минимум 2 символа.");
      return;
    }

    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(cleanCode)) {
      setError(
        "Код должен содержать латинские буквы, цифры и дефисы.",
      );
      return;
    }

    setSaving(true);

    try {
      await apiRequest<City>("/cities", {
        method: "POST",
        body: JSON.stringify({
          name: cleanName,
          code: cleanCode,
        }),
      });

      setName("");
      setCode("");
      setSuccess("Город успешно создан.");

      await loadCities();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Не удалось создать город",
      );
    } finally {
      setSaving(false);
    }
  }

  function startEditing(city: City) {
    setEditingId(city.id);
    setEditName(city.name);
    setEditCode(city.code);
    setError("");
    setSuccess("");
  }

  function cancelEditing() {
    setEditingId("");
    setEditName("");
    setEditCode("");
  }

  async function handleUpdate(
    event: FormEvent<HTMLFormElement>,
    city: City,
  ) {
    event.preventDefault();

    setError("");
    setSuccess("");

    const cleanName = editName.trim();
    const cleanCode = editCode.trim().toLowerCase();

    if (cleanName.length < 2) {
      setError("Название города должно содержать минимум 2 символа.");
      return;
    }

    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(cleanCode)) {
      setError(
        "Код должен содержать латинские буквы, цифры и дефисы.",
      );
      return;
    }

    setActionId(city.id);

    try {
      const updated = await apiRequest<City>(
        `/cities/${city.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            name: cleanName,
            code: cleanCode,
          }),
        },
      );

      setCities((current) =>
        current.map((item) =>
          item.id === city.id ? updated : item,
        ),
      );

      cancelEditing();
      setSuccess("Данные города обновлены.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Не удалось обновить город",
      );
    } finally {
      setActionId("");
    }
  }

  async function toggleCity(city: City) {
    const nextActive = !city.is_active;

    const confirmed = window.confirm(
      nextActive
        ? `Активировать город «${city.name}»?`
        : `Отключить город «${city.name}»?`,
    );

    if (!confirmed) return;

    setActionId(city.id);
    setError("");
    setSuccess("");

    try {
      const updated = await apiRequest<City>(
        `/cities/${city.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            is_active: nextActive,
          }),
        },
      );

      setCities((current) =>
        current.map((item) =>
          item.id === city.id ? updated : item,
        ),
      );

      setSuccess(
        nextActive
          ? "Город активирован."
          : "Город отключён.",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Не удалось изменить состояние города",
      );
    } finally {
      setActionId("");
    }
  }

  return (
    <section className="org-page">
      <div className="org-header">
        <div>
          <h1>Города и населённые пункты</h1>
          <p>Управление географией работы платформы VEXA</p>
        </div>

        <div className="org-header-actions">
          <button
            type="button"
            className="org-button org-button-secondary"
            onClick={() => void loadCities()}
            disabled={loading}
          >
            {loading ? "Загрузка..." : "Обновить"}
          </button>

          {onBack && (
            <button
              type="button"
              className="org-button org-button-secondary"
              onClick={onBack}
            >
              Назад
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="org-message org-message-error" role="alert">
          {error}
        </div>
      )}

      {success && (
        <div className="org-message org-message-success" role="status">
          {success}
        </div>
      )}

      <div className="org-card">
        <h2>Добавить город</h2>

        <form className="org-create-form" onSubmit={handleCreate}>
          <label>
            Название города
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Например, Оболенск"
              minLength={2}
              maxLength={120}
              required
              disabled={saving}
            />
          </label>

          <label>
            Код города
            <input
              type="text"
              value={code}
              onChange={(event) =>
                setCode(event.target.value.toLowerCase())
              }
              placeholder="Например, obolensk"
              minLength={2}
              maxLength={80}
              required
              disabled={saving}
            />
          </label>

          <div className="org-form-hint">
            Используйте латинские буквы, цифры и дефисы.
            Код должен быть уникальным.
          </div>

          <button
            type="submit"
            className="org-button org-button-primary"
            disabled={saving}
          >
            {saving ? "Создание..." : "Добавить город"}
          </button>
        </form>
      </div>

      <div className="org-card">
        <div className="org-section-heading">
          <div>
            <h2>Список городов</h2>
            <p>
              Всего: {cities.length} · Активных:{" "}
              {cities.filter((city) => city.is_active).length}
            </p>
          </div>
        </div>

        {loading ? (
          <p className="org-empty">Загрузка городов...</p>
        ) : cities.length === 0 ? (
          <p className="org-empty">
            Города пока не добавлены.
          </p>
        ) : (
          <div className="org-list">
            {cities.map((city) => (
              <article className="org-list-item" key={city.id}>
                <div className="org-list-main">
                  {editingId === city.id ? (
                    <form
                      className="org-create-form"
                      onSubmit={(event) =>
                        void handleUpdate(event, city)
                      }
                    >
                      <label>
                        Название города
                        <input
                          value={editName}
                          onChange={(event) =>
                            setEditName(event.target.value)
                          }
                          minLength={2}
                          maxLength={120}
                          required
                        />
                      </label>

                      <label>
                        Код города
                        <input
                          value={editCode}
                          onChange={(event) =>
                            setEditCode(event.target.value.toLowerCase())
                          }
                          minLength={2}
                          maxLength={80}
                          required
                        />
                      </label>

                      <div className="org-header-actions">
                        <button
                          type="submit"
                          className="org-button org-button-primary"
                          disabled={actionId === city.id}
                        >
                          {actionId === city.id
                            ? "Сохранение..."
                            : "Сохранить"}
                        </button>

                        <button
                          type="button"
                          className="org-button org-button-secondary"
                          onClick={cancelEditing}
                          disabled={actionId === city.id}
                        >
                          Отмена
                        </button>
                      </div>
                    </form>
                  ) : (
                    <>
                      <h3>{city.name}</h3>
                      <p>Код: {city.code}</p>
                      <p>Создан: {formatDate(city.created_at)}</p>
                      <span
                        className={`org-status ${
                          city.is_active
                            ? "org-status-active"
                            : "org-status-suspended"
                        }`}
                      >
                        {city.is_active ? "Активен" : "Отключён"}
                      </span>
                    </>
                  )}
                </div>

                {editingId !== city.id && (
                  <div className="org-list-actions">
                    <button
                      type="button"
                      className="org-button org-button-secondary"
                      onClick={() => startEditing(city)}
                      disabled={actionId !== ""}
                    >
                      Изменить
                    </button>

                    <button
                      type="button"
                      className={`org-button ${
                        city.is_active
                          ? "org-button-danger"
                          : "org-button-primary"
                      }`}
                      onClick={() => void toggleCity(city)}
                      disabled={actionId !== ""}
                    >
                      {actionId === city.id
                        ? "Сохранение..."
                        : city.is_active
                          ? "Отключить"
                          : "Активировать"}
                    </button>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
