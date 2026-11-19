
import { useCallback, useEffect, useState, type FormEvent } from "react";

const API_BASE = "/api/v1/platform-admin";

type OrganizationStatus = "pending" | "active" | "suspended" | "rejected";

type Organization = {
  id: string;
  name: string;
  slug: string;
  status: OrganizationStatus;
  created_at?: string;
  updated_at?: string;
};

type City = {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
};

type OrganizationDetail = {
  id: string;
  name: string;
  slug: string;
  status: OrganizationStatus;
  cities: Array<{
    city_id: string;
    is_active: boolean;
  }>;
  branches: Array<{
    branch_id: string;
    is_active: boolean;
  }>;
};

type OrganizationsResponse = {
  items: Organization[];
  limit: number;
  offset: number;
};

type CitiesResponse = {
  items: City[];
};

type Props = {
  token: string;
  onBack?: () => void;
};

const STATUS_LABELS: Record<OrganizationStatus, string> = {
  pending: "Ожидает проверки",
  active: "Активна",
  suspended: "Приостановлена",
  rejected: "Отклонена",
};

const STATUS_OPTIONS: OrganizationStatus[] = [
  "pending",
  "active",
  "suspended",
  "rejected",
];

function getApiError(data: unknown): string {
  if (!data || typeof data !== "object") {
    return "Не удалось выполнить запрос";
  }

  const detail = (data as { detail?: unknown }).detail;

  if (typeof detail === "string") {
    return detail;
  }

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

export default function Organizations({ token, onBack }: Props) {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [filter, setFilter] = useState<"all" | OrganizationStatus>("all");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [creating, setCreating] = useState(false);

  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [detail, setDetail] = useState<OrganizationDetail | null>(null);
  const [cities, setCities] = useState<City[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [cityAction, setCityAction] = useState("");

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

  const loadOrganizations = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const params = new URLSearchParams({
        limit: "100",
        offset: "0",
      });

      if (filter !== "all") {
        params.set("status", filter);
      }

      const result = await apiRequest<OrganizationsResponse>(
        `/organizations?${params.toString()}`,
      );

      setOrganizations(result.items || []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Ошибка загрузки организаций",
      );
    } finally {
      setLoading(false);
    }
  }, [filter, token]);

  const loadOrganizationDetail = useCallback(
    async (organizationId: string) => {
      setSelectedOrgId(organizationId);
      setDetailLoading(true);
      setError("");
      setSuccess("");

      try {
        const [organization, cityCatalog] = await Promise.all([
          apiRequest<OrganizationDetail>(
            `/organizations/${organizationId}`,
          ),
          apiRequest<CitiesResponse>(
            "/organizations/catalog/cities?active_only=true",
          ),
        ]);

        setDetail(organization);
        setCities(cityCatalog.items || []);
      } catch (err) {
        setDetail(null);
        setError(
          err instanceof Error
            ? err.message
            : "Не удалось загрузить информацию об организации",
        );
      } finally {
        setDetailLoading(false);
      }
    },
    [token],
  );

  useEffect(() => {
    void loadOrganizations();
  }, [loadOrganizations]);

  function generateSlug(value: string): string {
    return value
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 120);
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setSuccess("");

    const cleanName = name.trim();
    const cleanSlug = slug.trim().toLowerCase();

    if (cleanName.length < 2) {
      setError("Название организации должно содержать минимум 2 символа.");
      return;
    }

    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(cleanSlug)) {
      setError(
        "Идентификатор должен содержать только латинские буквы, цифры и дефисы.",
      );
      return;
    }

    setCreating(true);

    try {
      const created = await apiRequest<Organization>(
        "/organizations",
        {
          method: "POST",
          body: JSON.stringify({
            name: cleanName,
            slug: cleanSlug,
          }),
        },
      );

      setName("");
      setSlug("");
      setSuccess("Организация успешно создана.");

      await loadOrganizations();
      await loadOrganizationDetail(created.id);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Не удалось создать организацию",
      );
    } finally {
      setCreating(false);
    }
  }

  async function changeStatus(
    organization: Organization,
    newStatus: OrganizationStatus,
  ) {
    if (organization.status === newStatus) return;

    const confirmed = window.confirm(
      `Изменить статус организации «${organization.name}» на «${STATUS_LABELS[newStatus]}»?`,
    );

    if (!confirmed) return;

    setError("");
    setSuccess("");

    try {
      await apiRequest(
        `/organizations/${organization.id}/status`,
        {
          method: "PATCH",
          body: JSON.stringify({ status: newStatus }),
        },
      );

      setSuccess("Статус организации изменён.");
      await loadOrganizations();

      if (selectedOrgId === organization.id) {
        await loadOrganizationDetail(organization.id);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Не удалось изменить статус",
      );
    }
  }

  async function changeCityAssignment(
    cityId: string,
    assigned: boolean,
  ) {
    if (!selectedOrgId) return;

    setCityAction(cityId);
    setError("");
    setSuccess("");

    try {
      const method = assigned ? "DELETE" : "POST";

      await apiRequest(
        `/organizations/${selectedOrgId}/cities/${cityId}`,
        { method },
      );

      setSuccess(
        assigned
          ? "Город отключён от организации."
          : "Город подключён к организации.",
      );

      await loadOrganizationDetail(selectedOrgId);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Не удалось изменить привязку города",
      );
    } finally {
      setCityAction("");
    }
  }

  function isCityAssigned(cityId: string): boolean {
    return Boolean(
      detail?.cities?.some(
        (item) => item.city_id === cityId && item.is_active,
      ),
    );
  }

  return (
    <section className="org-page">
      <div className="org-header">
        <div>
          <h1>Организации</h1>
          <p>Управление организациями платформы VEXA</p>
        </div>

        <div className="org-header-actions">
          <button
            type="button"
            className="org-button org-button-secondary"
            onClick={() => void loadOrganizations()}
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
        <h2>Создать организацию</h2>

        <form className="org-create-form" onSubmit={handleCreate}>
          <label>
            Название организации
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Например, VEXA Оболенск"
              minLength={2}
              maxLength={200}
              required
            />
          </label>

          <label>
            Идентификатор организации (slug)
            <input
              type="text"
              value={slug}
              onChange={(event) =>
                setSlug(event.target.value.toLowerCase())
              }
              placeholder="Например, vexa-obolensk"
              minLength={2}
              maxLength={120}
              required
            />
          </label>

          <div className="org-form-hint">
            Только латинские буквы, цифры и дефисы. Идентификатор должен быть
            уникальным.
          </div>

          <button
            type="submit"
            className="org-button org-button-primary"
            disabled={creating}
          >
            {creating ? "Создание..." : "Создать организацию"}
          </button>
        </form>
      </div>

      <div className="org-card">
        <div className="org-section-heading">
          <div>
            <h2>Список организаций</h2>
            <p>Всего в текущем списке: {organizations.length}</p>
          </div>

          <select
            value={filter}
            onChange={(event) =>
              setFilter(event.target.value as "all" | OrganizationStatus)
            }
            aria-label="Фильтр организаций по статусу"
          >
            <option value="all">Все статусы</option>
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>
                {STATUS_LABELS[status]}
              </option>
            ))}
          </select>
        </div>

        {loading ? (
          <p className="org-empty">Загрузка организаций...</p>
        ) : organizations.length === 0 ? (
          <p className="org-empty">Организации не найдены.</p>
        ) : (
          <div className="org-list">
            {organizations.map((organization) => (
              <article
                key={organization.id}
                className={`org-list-item ${
                  selectedOrgId === organization.id
                    ? "org-list-item-selected"
                    : ""
                }`}
              >
                <div className="org-list-main">
                  <h3>{organization.name}</h3>
                  <p>Идентификатор: {organization.slug}</p>
                  <p>
                    Создана: {formatDate(organization.created_at)}
                  </p>
                  <span className={`org-status org-status-${organization.status}`}>
                    {STATUS_LABELS[organization.status]}
                  </span>
                </div>

                <div className="org-list-actions">
                  <button
                    type="button"
                    className="org-button org-button-secondary"
                    onClick={() =>
                      void loadOrganizationDetail(organization.id)
                    }
                  >
                    Открыть
                  </button>

                  <label className="org-status-control">
                    Статус
                    <select
                      value={organization.status}
                      onChange={(event) =>
                        void changeStatus(
                          organization,
                          event.target.value as OrganizationStatus,
                        )
                      }
                    >
                      {STATUS_OPTIONS.map((status) => (
                        <option key={status} value={status}>
                          {STATUS_LABELS[status]}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>

      {selectedOrgId && (
        <div className="org-card">
          <div className="org-section-heading">
            <div>
              <h2>Управление организацией</h2>
              <p>
                Настройка городов, подключённых к выбранной организации.
              </p>
            </div>

            <button
              type="button"
              className="org-button org-button-secondary"
              onClick={() => {
                setSelectedOrgId("");
                setDetail(null);
              }}
            >
              Закрыть
            </button>
          </div>

          {detailLoading ? (
            <p className="org-empty">Загрузка информации...</p>
          ) : detail ? (
            <>
              <div className="org-detail-info">
                <div>
                  <span>Название</span>
                  <strong>{detail.name}</strong>
                </div>

                <div>
                  <span>Идентификатор</span>
                  <strong>{detail.slug}</strong>
                </div>

                <div>
                  <span>Статус</span>
                  <strong>{STATUS_LABELS[detail.status]}</strong>
                </div>
              </div>

              <div className="org-city-section">
                <h3>Города организации</h3>
                <p>
                  Подключайте города, в которых организация будет работать.
                </p>

                {cities.length === 0 ? (
                  <p className="org-empty">
                    В каталоге пока нет активных городов.
                  </p>
                ) : (
                  <div className="org-city-list">
                    {cities.map((city) => {
                      const assigned = isCityAssigned(city.id);

                      return (
                        <div className="org-city-item" key={city.id}>
                          <div>
                            <strong>{city.name}</strong>
                            <span>Код: {city.code}</span>
                            <span>
                              {assigned
                                ? "Подключён к организации"
                                : "Не подключён"}
                            </span>
                          </div>

                          <button
                            type="button"
                            className={`org-button ${
                              assigned
                                ? "org-button-danger"
                                : "org-button-primary"
                            }`}
                            disabled={cityAction !== ""}
                            onClick={() =>
                              void changeCityAssignment(city.id, assigned)
                            }
                          >
                            {cityAction === city.id
                              ? "Сохранение..."
                              : assigned
                                ? "Отключить"
                                : "Подключить"}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="org-form-hint">
                Филиалы будут настраиваться отдельно. Сейчас доступно
                управление организациями и подключением городов.
              </div>
            </>
          ) : (
            <p className="org-empty">
              Не удалось получить информацию об организации.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

