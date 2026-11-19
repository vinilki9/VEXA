
import React, { useCallback, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  LayoutDashboard,
  Map,
  CarFront,
  Users,
  Wallet,
  Settings,
  Bell,
  RefreshCw,
  LogOut,
  CheckCircle2,
  Clock,
  AlertCircle,
} from 'lucide-react';
import './style.css';

const API_BASE = 'https://109.120.184.20';
const CITY_CODE = 'obolensk';
const TOKEN_KEY = 'vexa_dispatch_token';

type VexaOrder = {
  id: string;
  public_number: string;
  city_code: string;
  customer_name?: string | null;
  customer_phone?: string | null;
  pickup_address: string;
  destination_address: string;
  status: string;
  payment_method: string;
  price_rub: number;
  created_at: string;
  driver_user_id?: string | null;
};

type DispatcherProfile = {
  id: string;
  username: string;
  role: string;
  branch_id?: string | null;
};

async function apiRequest(
  path: string,
  token?: string,
  options: RequestInit = {},
) {
  const headers = new Headers(options.headers || {});
  headers.set('Content-Type', 'application/json');

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      data?.detail ||
      data?.message ||
      `Ошибка сервера: ${response.status}`,
    );
  }

  return data;
}

function formatDate(value: string) {
  if (!value) return '—';

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return '—';

  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getStatusLabel(status: string) {
  const labels: Record<string, string> = {
    new: 'Новый',
    accepted: 'Принят',
    assigned: 'Водитель назначен',
    arrived: 'Водитель на месте',
    in_progress: 'В пути',
    completed: 'Завершён',
    cancelled: 'Отменён',
  };

  return labels[status] || status;
}

function getStatusClass(status: string) {
  if (status === 'new' || status === 'accepted') return 'amber';
  if (status === 'assigned' || status === 'arrived') return 'blue';
  if (status === 'in_progress') return 'teal';
  return 'gray';
}

function getPaymentLabel(method: string) {
  const labels: Record<string, string> = {
    cash: 'Наличные',
    driver_transfer: 'Перевод водителю',
    card: 'Банковская карта',
    sbp: 'СБП',
  };

  return labels[method] || method || 'Не указан';
}

function LoginScreen({
  onLogin,
}: {
  onLogin: (username: string, password: string) => Promise<void>;
}) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      await onLogin(username.trim(), password);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Не удалось войти',
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        padding: 20,
        background: '#f5f7fa',
      }}
    >
      <form
        onSubmit={submit}
        style={{
          width: '100%',
          maxWidth: 390,
          background: '#fff',
          border: '1px solid #e8edf2',
          borderRadius: 18,
          padding: 30,
          boxShadow: '0 10px 35px #1d293912',
        }}
      >
        <div className="brand" style={{ margin: '0 0 28px' }}>
          <span className="mark">V</span>
          <b>VEXA</b>
          <small>DISPATCH</small>
        </div>

        <h1 style={{ fontSize: 23, marginBottom: 8 }}>
          Вход диспетчера
        </h1>

        <p style={{ color: '#8994a3', fontSize: 13, marginBottom: 24 }}>
          Войдите в панель управления VEXA
        </p>

        <label style={{ display: 'block', fontSize: 12, marginBottom: 7 }}>
          Логин
        </label>

        <input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
          required
          style={inputStyle}
          placeholder="Введите логин"
        />

        <label
          style={{
            display: 'block',
            fontSize: 12,
            margin: '16px 0 7px',
          }}
        >
          Пароль
        </label>

        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
          style={inputStyle}
          placeholder="Введите пароль"
        />

        {error && (
          <div style={errorStyle}>
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          style={{
            ...primaryButtonStyle,
            width: '100%',
            marginTop: 22,
            opacity: loading ? 0.65 : 1,
          }}
        >
          {loading ? 'Выполняется вход...' : 'Войти'}
        </button>

        <p
          style={{
            color: '#a0aab7',
            fontSize: 10,
            textAlign: 'center',
            marginTop: 20,
          }}
        >
          VEXA · Система управления заказами
        </p>
      </form>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  height: 43,
  border: '1px solid #dfe6eb',
  borderRadius: 8,
  padding: '0 12px',
  fontSize: 13,
  outline: 'none',
  background: '#fff',
};

const primaryButtonStyle: React.CSSProperties = {
  border: 0,
  borderRadius: 8,
  background: '#20b8aa',
  color: '#fff',
  padding: '11px 15px',
  fontSize: 12,
  fontWeight: 700,
  cursor: 'pointer',
};

const errorStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  color: '#b42318',
  background: '#fff0ee',
  borderRadius: 8,
  padding: 10,
  fontSize: 11,
  marginTop: 15,
};

function App() {
  const [token, setToken] = useState<string | null>(null);
  const [dispatcher, setDispatcher] = useState<DispatcherProfile | null>(null);
  const [orders, setOrders] = useState<VexaOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [acceptingId, setAcceptingId] = useState<string | null>(null);

  const loadOrders = useCallback(async (accessToken: string) => {
    setLoading(true);
    setError('');

    try {
      const data = await apiRequest(
        `/api/v1/dispatch/orders?city_code=${CITY_CODE}`,
        accessToken,
      );

      setOrders(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Не удалось загрузить заказы',
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const loadProfile = useCallback(async (accessToken: string) => {
    const profile = await apiRequest(
      '/api/v1/dispatch/auth/me',
      accessToken,
    );

    setDispatcher(profile);
  }, []);

  useEffect(() => {
    const savedToken = localStorage.getItem(TOKEN_KEY);

    if (savedToken) {
      setToken(savedToken);

      Promise.all([
        loadProfile(savedToken),
        loadOrders(savedToken),
      ]).catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setDispatcher(null);
      });
    }
  }, [loadOrders, loadProfile]);

  useEffect(() => {
    if (!token) return;

    const interval = window.setInterval(() => {
      loadOrders(token);
    }, 15000);

    return () => window.clearInterval(interval);
  }, [token, loadOrders]);

  async function login(username: string, password: string) {
    const result = await apiRequest(
      '/api/v1/dispatch/auth/login',
      undefined,
      {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      },
    );

    if (!result?.access_token) {
      throw new Error('Сервер не вернул токен авторизации');
    }

    const accessToken = result.access_token;

    await loadProfile(accessToken);

    localStorage.setItem(TOKEN_KEY, accessToken);
    setToken(accessToken);

    await loadOrders(accessToken);
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setDispatcher(null);
    setOrders([]);
    setError('');
    setNotice('');
  }

  async function acceptOrder(order: VexaOrder) {
    if (!token || acceptingId) return;

    setAcceptingId(order.id);
    setError('');
    setNotice('');

    try {
      const result = await apiRequest(
        `/api/v1/dispatch/orders/${order.id}/accept`,
        token,
        { method: 'POST' },
      );

      if (result.assigned) {
        setNotice(
          `Заказ ${order.public_number}: водитель назначен автоматически.`,
        );
      } else {
        setNotice(
          `Заказ ${order.public_number} принят. Свободных водителей нет — требуется ручное назначение.`,
        );
      }

      await loadOrders(token);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Не удалось принять заказ',
      );
    } finally {
      setAcceptingId(null);
    }
  }

  if (!token) {
    return <LoginScreen onLogin={login} />;
  }

  const newOrders = orders.filter((order) => order.status === 'new');
  const acceptedOrders = orders.filter(
    (order) => order.status === 'accepted',
  );
  const activeOrders = orders.filter((order) =>
    ['assigned', 'arrived', 'in_progress'].includes(order.status),
  );
  const completedOrders = orders.filter(
    (order) => order.status === 'completed',
  );

  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <span className="mark">V</span>
          <b>VEXA</b>
          <small>DISPATCH</small>
        </div>

        <nav>
          <a className="active">
            <LayoutDashboard />
            Обзор
          </a>
          <a>
            <Map />
            Карта
          </a>
          <a>
            <CarFront />
            Заказы
          </a>
          <a>
            <Users />
            Водители
          </a>
          <a>
            <Wallet />
            Финансы
          </a>
          <a>
            <Settings />
            Настройки
          </a>
        </nav>

        <div className="branch">
          <span className="dot" />
          Оболенск · Пилотный город
        </div>
      </aside>

      <main>
        <header>
          <div>
            <p className="eyebrow">ПАНЕЛЬ УПРАВЛЕНИЯ</p>
            <h1>Обзор диспетчера</h1>
            <p style={{ color: '#8994a3', fontSize: 11, marginTop: 7 }}>
              {dispatcher?.username || 'Диспетчер'} · Оболенск
            </p>
          </div>

          <div className="headright">
            <span className="online">
              <i />
              Сервер подключён
            </span>

            <button
              onClick={() => loadOrders(token)}
              title="Обновить заказы"
              style={iconButtonStyle}
            >
              <RefreshCw size={17} />
            </button>

            <Bell />

            <button
              onClick={logout}
              title="Выйти из системы"
              style={iconButtonStyle}
            >
              <LogOut size={17} />
            </button>
          </div>
        </header>

        {error && (
          <div style={errorStyle}>
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        {notice && (
          <div style={successStyle}>
            <CheckCircle2 size={16} />
            {notice}
            <button
              onClick={() => setNotice('')}
              style={{
                marginLeft: 'auto',
                border: 0,
                background: 'transparent',
                cursor: 'pointer',
                color: 'inherit',
              }}
            >
              ×
            </button>
          </div>
        )}

        <section className="stats">
          <article>
            <label>Новые заказы</label>
            <strong>{newOrders.length}</strong>
            <small>Ожидают принятия</small>
          </article>

          <article>
            <label>Ожидают водителя</label>
            <strong>{acceptedOrders.length}</strong>
            <small>Нуждается в назначении</small>
          </article>

          <article>
            <label>Активные поездки</label>
            <strong>{activeOrders.length}</strong>
            <small>Назначены водители</small>
          </article>

          <article>
            <label>Завершённые</label>
            <strong>{completedOrders.length}</strong>
            <small>В загруженном списке</small>
          </article>
        </section>

        <section className="content">
          <article className="mapcard">
            <div className="cardhead">
              <div>
                <h2>Карта города</h2>
                <p>Географическое отображение будет подключено отдельно</p>
              </div>
              <span className="live">
                <i />
                ОБОЛЕНСК
              </span>
            </div>

            <div
              className="maparea"
              style={{
                display: 'grid',
                placeItems: 'center',
                padding: 25,
                textAlign: 'center',
              }}
            >
              <div style={{ color: '#63756e', maxWidth: 280 }}>
                <Map
                  size={38}
                  style={{
                    margin: '0 auto 13px',
                    color: '#159b8f',
                  }}
                />
                <b style={{ display: 'block', fontSize: 14 }}>
                  Географическая карта
                </b>
                <p style={{ fontSize: 11, lineHeight: 1.6 }}>
                  Здесь будет отображаться карта Оболенска,
                  местоположение автомобилей и активные заказы.
                </p>
              </div>
            </div>
          </article>

          <article className="orders">
            <div className="cardhead">
              <div>
                <h2>Заказы</h2>
                <p>
                  {orders.length} заказов в текущем списке
                </p>
              </div>

              <button onClick={() => loadOrders(token)}>
                Обновить
              </button>
            </div>

            {loading && orders.length === 0 && (
              <p style={{ color: '#8994a3', fontSize: 12 }}>
                Загрузка заказов...
              </p>
            )}

            {!loading && orders.length === 0 && (
              <p style={{ color: '#8994a3', fontSize: 12 }}>
                Заказов пока нет.
              </p>
            )}

            {orders.map((order) => (
              <div className="order" key={order.id}>
                <div className="ordericon">
                  <CarFront />
                </div>

                <div className="orderinfo">
                  <b>{order.public_number}</b>

                  <span>
                    {order.pickup_address} → {order.destination_address}
                  </span>

                  <small>
                    {formatDate(order.created_at)}
                    {' · '}
                    {getPaymentLabel(order.payment_method)}
                    {' · '}
                    {Number(order.price_rub || 0).toLocaleString('ru-RU')} ₽
                  </small>

                  <small>
                    Клиент: {order.customer_name || 'Имя не указано'}
                    {order.customer_phone
                      ? ` · ${order.customer_phone}`
                      : ''}
                  </small>

                  <span
                    className={`status ${getStatusClass(order.status)}`}
                    style={{
                      display: 'inline-block',
                      width: 'fit-content',
                      marginTop: 5,
                    }}
                  >
                    {getStatusLabel(order.status)}
                  </span>

                  {order.status === 'new' && (
                    <button
                      onClick={() => acceptOrder(order)}
                      disabled={acceptingId !== null}
                      style={{
                        ...primaryButtonStyle,
                        marginTop: 8,
                        width: 'fit-content',
                        opacity: acceptingId !== null ? 0.6 : 1,
                      }}
                    >
                      {acceptingId === order.id
                        ? 'Принимаем...'
                        : 'Принять и найти водителя'}
                    </button>
                  )}

                  {order.status === 'accepted' && (
                    <small style={{ color: '#ad7b1d', marginTop: 5 }}>
                      Требуется назначить водителя вручную
                    </small>
                  )}
                </div>
              </div>
            ))}
          </article>
        </section>

        <section className="bottom">
          <div>
            <Clock />
            <b>Обновление заказов</b>
            <span>
              Автоматическое обновление каждые 15 секунд.
              Данные загружаются с сервера VEXA.
            </span>
          </div>
        </section>
      </main>
    </div>
  );
}

const iconButtonStyle: React.CSSProperties = {
  border: 0,
  background: 'transparent',
  color: '#64748b',
  padding: 5,
  cursor: 'pointer',
  display: 'grid',
  placeItems: 'center',
};

const successStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  color: '#087e70',
  background: '#e8f8f4',
  borderRadius: 9,
  padding: 12,
  fontSize: 11,
  marginBottom: 15,
};

createRoot(document.getElementById('root')!).render(<App />);
