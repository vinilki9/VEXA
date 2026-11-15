
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
  UserCheck,
  X,
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

type AvailableVehicle = {
  id: string;
  make: string;
  model: string;
  color: string;
  license_plate: string;
};

type AvailableDriver = {
  driver_user_id: string;
  username: string;
  phone?: string | null;
  rating: string;
  is_online: boolean;
  location?: {
    latitude: number;
    longitude: number;
    recorded_at: string;
  } | null;
  vehicle: AvailableVehicle;
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

const secondaryButtonStyle: React.CSSProperties = {
  border: '1px solid #dfe6eb',
  borderRadius: 8,
  background: '#fff',
  color: '#526174',
  padding: '10px 14px',
  fontSize: 12,
  fontWeight: 600,
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

function App() {
  const [token, setToken] = useState<string | null>(null);
  const [dispatcher, setDispatcher] = useState<DispatcherProfile | null>(null);
  const [orders, setOrders] = useState<VexaOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [acceptingId, setAcceptingId] = useState<string | null>(null);

  const [assignmentOrder, setAssignmentOrder] = useState<VexaOrder | null>(null);
  const [availableDrivers, setAvailableDrivers] = useState<AvailableDriver[]>([]);
  const [selectedDriver, setSelectedDriver] = useState<AvailableDriver | null>(null);
  const [loadingDrivers, setLoadingDrivers] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [assignmentError, setAssignmentError] = useState('');

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
    closeAssignment();
  }

  function closeAssignment() {
    setAssignmentOrder(null);
    setAvailableDrivers([]);
    setSelectedDriver(null);
    setAssignmentError('');
    setLoadingDrivers(false);
    setAssigning(false);
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

  async function openManualAssignment(order: VexaOrder) {
    if (!token) return;

    setAssignmentOrder(order);
    setAvailableDrivers([]);
    setSelectedDriver(null);
    setAssignmentError('');
    setLoadingDrivers(true);

    try {
      const result = await apiRequest(
        `/api/v1/dispatch/orders/${order.id}/available-drivers`,
        token,
      );

      const drivers: AvailableDriver[] = Array.isArray(result?.drivers)
        ? result.drivers
        : [];

      setAvailableDrivers(drivers);

      if (drivers.length === 0) {
        setAssignmentError(
          'Сейчас нет свободных водителей с подходящим автомобилем в этом филиале.',
        );
      }
    } catch (err) {
      setAssignmentError(
        err instanceof Error
          ? err.message
          : 'Не удалось загрузить список водителей',
      );
    } finally {
      setLoadingDrivers(false);
    }
  }

  async function assignSelectedDriver() {
    if (!token || !assignmentOrder || !selectedDriver || assigning) return;

    setAssigning(true);
    setAssignmentError('');
    setError('');

    try {
      await apiRequest(
        `/api/v1/dispatch/orders/${assignmentOrder.id}/assign`,
        token,
        {
          method: 'POST',
          body: JSON.stringify({
            driver_user_id: selectedDriver.driver_user_id,
            vehicle_id: selectedDriver.vehicle.id,
          }),
        },
      );

      setNotice(
        `Заказ ${assignmentOrder.public_number}: водитель ${selectedDriver.username} назначен вручную.`,
      );

      closeAssignment();
      await loadOrders(token);
    } catch (err) {
      setAssignmentError(
        err instanceof Error
          ? err.message
          : 'Не удалось назначить водителя',
      );
    } finally {
      setAssigning(false);
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
            <small>Нуждаются в назначении</small>
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
                <p>{orders.length} заказов в текущем списке</p>
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
                    Клиент: {order.customer_name || 'Анонимный заказ'}
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
                    <button
                      onClick={() => openManualAssignment(order)}
                      style={{
                        ...primaryButtonStyle,
                        marginTop: 8,
                        width: 'fit-content',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 7,
                      }}
                    >
                      <UserCheck size={15} />
                      Назначить водителя
                    </button>
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

      {assignmentOrder && (
        <div style={modalOverlayStyle}>
          <div style={modalStyle}>
            <div style={modalHeaderStyle}>
              <div>
                <h2 style={{ margin: 0, fontSize: 18 }}>
                  Назначение водителя
                </h2>
                <p style={{ margin: '6px 0 0', color: '#8994a3', fontSize: 12 }}>
                  Заказ {assignmentOrder.public_number}
                </p>
              </div>

              <button
                onClick={closeAssignment}
                disabled={assigning}
                style={iconButtonStyle}
                title="Закрыть"
              >
                <X size={20} />
              </button>
            </div>

            <div style={{ margin: '16px 0', fontSize: 12, color: '#526174' }}>
              <div>
                <b>Откуда:</b> {assignmentOrder.pickup_address}
              </div>
              <div style={{ marginTop: 5 }}>
                <b>Куда:</b> {assignmentOrder.destination_address}
              </div>
            </div>

            <div style={modalDividerStyle} />

            <h3 style={{ fontSize: 13, margin: '15px 0 10px' }}>
              Свободные водители
            </h3>

            {loadingDrivers && (
              <p style={{ color: '#8994a3', fontSize: 12 }}>
                Загружаем список водителей...
              </p>
            )}

            {!loadingDrivers && availableDrivers.length === 0 && (
              <div style={emptyDriversStyle}>
                <Users size={25} />
                <p style={{ margin: '9px 0 0' }}>
                  Подходящих свободных водителей пока нет.
                </p>
              </div>
            )}

            {availableDrivers.length > 0 && (
              <div style={driverListStyle}>
                {availableDrivers.map((driver) => {
                  const isSelected =
                    selectedDriver?.driver_user_id === driver.driver_user_id &&
                    selectedDriver?.vehicle.id === driver.vehicle.id;

                  return (
                    <button
                      key={`${driver.driver_user_id}-${driver.vehicle.id}`}
                      onClick={() => setSelectedDriver(driver)}
                      style={{
                        ...driverCardStyle,
                        border: isSelected
                          ? '2px solid #20b8aa'
                          : '1px solid #e4eaf0',
                        background: isSelected ? '#effbf9' : '#fff',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={driverAvatarStyle}>
                          <CarFront size={19} />
                        </div>

                        <div style={{ flex: 1, textAlign: 'left' }}>
                          <b style={{ display: 'block', fontSize: 13, color: '#172033' }}>
                            {driver.username}
                          </b>
                          <span style={{ fontSize: 11, color: '#8994a3' }}>
                            {driver.phone || 'Телефон не указан'}
                          </span>
                        </div>

                        <span style={ratingStyle}>
                          ★ {Number(driver.rating || 0).toFixed(1)}
                        </span>
                      </div>

                      <div style={vehicleInfoStyle}>
                        <b>
                          {[driver.vehicle.make, driver.vehicle.model]
                            .filter(Boolean)
                            .join(' ') || 'Автомобиль'}
                        </b>
                        <span>
                          {[driver.vehicle.color, driver.vehicle.license_plate]
                            .filter(Boolean)
                            .join(' · ')}
                        </span>
                      </div>

                      {driver.location && (
                        <small style={{ display: 'block', color: '#8994a3', marginTop: 7 }}>
                          GPS: {Number(driver.location.latitude).toFixed(5)},{' '}
                          {Number(driver.location.longitude).toFixed(5)}
                        </small>
                      )}

                      {isSelected && (
                        <span style={selectedLabelStyle}>
                          <CheckCircle2 size={14} />
                          Выбран
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}

            {assignmentError && (
              <div style={errorStyle}>
                <AlertCircle size={16} />
                {assignmentError}
              </div>
            )}

            <div style={modalActionsStyle}>
              <button
                onClick={closeAssignment}
                disabled={assigning}
                style={secondaryButtonStyle}
              >
                Отмена
              </button>

              <button
                onClick={assignSelectedDriver}
                disabled={!selectedDriver || assigning || loadingDrivers}
                style={{
                  ...primaryButtonStyle,
                  opacity: !selectedDriver || assigning ? 0.55 : 1,
                  cursor: !selectedDriver || assigning ? 'not-allowed' : 'pointer',
                }}
              >
                {assigning ? 'Назначаем...' : 'Подтвердить назначение'}
              </button>
            </div>
          </div>
        </div>
      )}
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

const modalOverlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  zIndex: 1000,
  background: 'rgba(15, 23, 42, 0.55)',
  display: 'grid',
  placeItems: 'center',
  padding: 16,
};

const modalStyle: React.CSSProperties = {
  width: '100%',
  maxWidth: 540,
  maxHeight: '90vh',
  overflowY: 'auto',
  background: '#fff',
  borderRadius: 16,
  padding: 22,
  boxShadow: '0 20px 60px #0003',
};

const modalHeaderStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
};

const modalDividerStyle: React.CSSProperties = {
  height: 1,
  background: '#edf0f3',
};

const driverListStyle: React.CSSProperties = {
  display: 'grid',
  gap: 9,
  maxHeight: 340,
  overflowY: 'auto',
};

const driverCardStyle: React.CSSProperties = {
  width: '100%',
  textAlign: 'left',
  padding: 13,
  borderRadius: 11,
  cursor: 'pointer',
};

const driverAvatarStyle: React.CSSProperties = {
  width: 36,
  height: 36,
  borderRadius: 9,
  background: '#e7f8f6',
  color: '#159b8f',
  display: 'grid',
  placeItems: 'center',
};

const ratingStyle: React.CSSProperties = {
  color: '#ad7b1d',
  fontSize: 12,
  fontWeight: 700,
};

const vehicleInfoStyle: React.CSSProperties = {
  display: 'grid',
  gap: 3,
  marginTop: 11,
  paddingTop: 9,
  borderTop: '1px solid #edf0f3',
  fontSize: 11,
  color: '#526174',
};

const selectedLabelStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 5,
  color: '#087e70',
  fontSize: 11,
  fontWeight: 700,
  marginTop: 9,
};

const emptyDriversStyle: React.CSSProperties = {
  padding: 25,
  textAlign: 'center',
  color: '#8994a3',
  background: '#f7f9fb',
  borderRadius: 10,
  fontSize: 12,
};

const modalActionsStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'flex-end',
  gap: 9,
  marginTop: 20,
  paddingTop: 15,
  borderTop: '1px solid #edf0f3',
};

createRoot(document.getElementById('root')!).render(<App />);
