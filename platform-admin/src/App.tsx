
import { useEffect, useState } from "react";
import Organizations from "./Organizations";

type AdminUser = {
  username: string;
};

const API_BASE = "/api/v1/platform-admin";

function App() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [token, setToken] = useState(
    () => sessionStorage.getItem("vexa_platform_admin_token") || "",
  );
  const [admin, setAdmin] = useState<AdminUser | null>(null);
  const [activeSection, setActiveSection] = useState<
    "organizations" | null
  >(null);

  useEffect(() => {
    if (!token) {
      setAdmin(null);
      return;
    }

    let cancelled = false;

    async function verifySession() {
      try {
        const response = await fetch(`${API_BASE}/organizations`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          throw new Error("Сессия недействительна");
        }

        if (!cancelled) {
          setAdmin({ username: "Главный администратор" });
        }
      } catch {
        sessionStorage.removeItem("vexa_platform_admin_token");
        if (!cancelled) {
          setToken("");
          setAdmin(null);
          setActiveSection(null);
          setError("Сессия завершена. Войдите снова.");
        }
      }
    }

    void verifySession();

    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handleLogin(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (!username.trim() || !password) {
      setError("Введите логин и пароль.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: username.trim(),
          password,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Не удалось выполнить вход. Проверьте данные.",
        );
      }

      if (!data.access_token) {
        throw new Error("Сервер не вернул токен авторизации.");
      }

      sessionStorage.setItem("vexa_platform_admin_token", data.access_token);
      setToken(data.access_token);
      setPassword("");
      setActiveSection(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Ошибка соединения с сервером.",
      );
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    sessionStorage.removeItem("vexa_platform_admin_token");
    setToken("");
    setAdmin(null);
    setPassword("");
    setError("");
    setActiveSection(null);
  }

  if (token && !admin) {
    return (
      <main className="auth-screen">
        <div className="auth-card loading-card">
          <div className="brand-mark">V</div>
          <h1>VEXA</h1>
          <p>Проверяем доступ к панели управления...</p>
          <div className="loader" />
        </div>
      </main>
    );
  }

  if (admin && activeSection === "organizations") {
    return (
      <Organizations
        token={token}
        onBack={() => setActiveSection(null)}
      />
    );
  }

  if (admin) {
    return (
      <main className="admin-screen">
        <header className="admin-header">
          <div className="brand">
            <div className="brand-mark">V</div>
            <div>
              <strong>VEXA</strong>
              <span>PLATFORM ADMIN</span>
            </div>
          </div>
          <button className="logout-button" onClick={handleLogout}>
            Выйти
          </button>
        </header>

        <section className="welcome-section">
          <span className="eyebrow">ЦЕНТРАЛЬНОЕ УПРАВЛЕНИЕ</span>
          <h1>Панель главного администратора</h1>
          <p>
            Управление платформой VEXA, организациями и развитием сервиса.
          </p>
        </section>

        <section className="admin-content">
          <div className="section-heading">
            <div>
              <h2>Рабочее пространство</h2>
              <p>Вы вошли как {admin.username}</p>
            </div>
            <span className="status-indicator">Доступ подтверждён</span>
          </div>

          <div className="module-grid">
            <button
              type="button"
              className="module-card module-card-clickable"
              onClick={() => setActiveSection("organizations")}
            >
              <span className="module-icon">⌂</span>
              <h3>Организации</h3>
              <p>Таксопарки и партнёрские организации.</p>
              <span className="module-status">Открыть раздел →</span>
            </button>

            <article className="module-card">
              <span className="module-icon">◎</span>
              <h3>Города и филиалы</h3>
              <p>География работы и территориальная структура.</p>
              <span className="module-status">Раздел готовится</span>
            </article>

            <article className="module-card">
              <span className="module-icon">▤</span>
              <h3>Заявки</h3>
              <p>Рассмотрение заявок партнёров и диспетчеров.</p>
              <span className="module-status">Раздел готовится</span>
            </article>

            <article className="module-card">
              <span className="module-icon">♙</span>
              <h3>Пользователи</h3>
              <p>Учётные записи и доступ к платформе.</p>
              <span className="module-status">Раздел готовится</span>
            </article>

            <article className="module-card">
              <span className="module-icon">₽</span>
              <h3>Финансы</h3>
              <p>Комиссии, начисления и финансовые операции.</p>
              <span className="module-status">Раздел готовится</span>
            </article>

            <article className="module-card">
              <span className="module-icon">⚙</span>
              <h3>Настройки платформы</h3>
              <p>Глобальные параметры и правила работы VEXA.</p>
              <span className="module-status">Раздел готовится</span>
            </article>
          </div>
        </section>

        <footer className="admin-footer">
          VEXA Platform Admin · Централизованное управление платформой
        </footer>
      </main>
    );
  }

  return (
    <main className="auth-screen">
      <div className="auth-layout">
        <section className="auth-intro">
          <div className="brand">
            <div className="brand-mark">V</div>
            <div>
              <strong>VEXA</strong>
              <span>PLATFORM ADMIN</span>
            </div>
          </div>

          <div className="intro-copy">
            <span className="eyebrow">ЕДИНАЯ ПЛАТФОРМА УПРАВЛЕНИЯ</span>
            <h1>
              Управляйте
              <br />
              развитием VEXA.
            </h1>
            <p>
              Центральная административная система для управления городами,
              организациями, партнёрами и всей инфраструктурой сервиса.
            </p>
          </div>

          <div className="intro-bottom">
            <span className="intro-line" />
            <span>VEXA · МОБИЛЬНОСТЬ БЕЗ ГРАНИЦ</span>
          </div>
        </section>

        <section className="auth-panel">
          <form className="auth-card" onSubmit={handleLogin}>
            <div className="mobile-brand">
              <div className="brand-mark">V</div>
              <strong>VEXA</strong>
            </div>

            <span className="eyebrow">ЗАЩИЩЁННЫЙ ДОСТУП</span>
            <h2>Вход в систему</h2>
            <p className="auth-description">
              Авторизуйтесь для доступа к панели главного администратора.
            </p>

            <label htmlFor="username">Логин</label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              placeholder="Введите логин"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              disabled={loading}
            />

            <label htmlFor="password">Пароль</label>
            <div className="password-field">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="Введите пароль"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={loading}
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
              >
                {showPassword ? "Скрыть" : "Показать"}
              </button>
            </div>

            {error && (
              <div className="error-message" role="alert">
                {error}
              </div>
            )}

            <button className="login-button" type="submit" disabled={loading}>
              {loading ? "Выполняется вход..." : "Войти в панель"}
            </button>

            <div className="security-note">
              <span>●</span>
              Доступ только для уполномоченного администратора
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}

export default App;
