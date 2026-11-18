import React, { useCallback, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  LayoutDashboard, Map, CarFront, Users, Wallet, Settings, Bell,
  RefreshCw, LogOut, CheckCircle2, Clock, AlertCircle, UserCheck, X,
  MapPin, Radio,
} from 'lucide-react';
import VexaMap from './components/VexaMap';
import DriverFinancePanel from './components/DriverFinancePanel';
import FinanceSummaryPanel from './components/FinanceSummaryPanel';
import './style.css';

const API_BASE = 'https://109.120.184.20';
const CITY_CODE = 'obolensk';
const TOKEN_KEY = 'vexa_dispatch_token';

type OrderTimelineEvent = {
  event_id: string;
  event_type: string;
  occurred_at: string;
  title: string;
  description?: string | null;
  actor?: string | null;
};

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
  timeline?: OrderTimelineEvent[];
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

type OnlineDriver = {
  user_id: string;
  username: string;
  phone?: string | null;
  is_online: boolean;
  rating: string;
  city?: { code: string; name: string };
  branch?: { name: string } | null;
  location?: {
    latitude: number;
    longitude: number;
    accuracy_meters?: number | null;
    recorded_at?: string | null;
    updated_at?: string | null;
  } | null;
};

async function apiRequest(
  path: string,
  token?: string,
  options: RequestInit = {},
) {
  const headers = new Headers(options.headers || {});
  headers.set('Content-Type', 'application/json');

  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      data?.detail || data?.message || `Ошибка сервера: ${response.status}`,
    );
  }

  return data;
}

function formatDate(value?: string | null) {
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
      setError(err instanceof Error ? err.message : 'Не удалось войти');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'grid',
      placeItems: 'center',
      padding: 20,
      background: '#f5f7fa',
    }}>
      <form onSubmit={submit} style={{
        width: '100%',
        maxWidth: 390,
        background: '#fff',
        border: '1px solid #e8edf2',
        borderRadius: 18,
        padding: 30,
        boxShadow: '0 10px 35px #1d293912',
      }}>
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
          onChange={e => setUsername(e.target.value)}
          autoComplete="username"
          required
          style={inputStyle}
          placeholder="Введите логин"
        />

        <label style={{
          display: 'block',
          fontSize: 12,
          margin: '16px 0 7px',
        }}>
          Пароль
        </label>

        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
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

        <button type="submit" disabled={loading} style={{
          ...primaryButtonStyle,
          width: '100%',
          marginTop: 22,
          opacity: loading ? 0.65 : 1,
        }}>
          {loading ? 'Выполняется вход...' : 'Войти'}
        </button>

        <p style={{
          color: '#a0aab7',
          fontSize: 10,
          textAlign: 'center',
          marginTop: 20,
        }}>
          VEXA · Система управления заказами
        </p>
      </form>
    </div>
  );
}

function App() {
  const [token, setToken] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<
    'overview' | 'map' | 'orders' | 'drivers' | 'finance'
  >('overview');
  const [dispatcher, setDispatcher] = useState<DispatcherProfile | null>(null);
  const [orders, setOrders] = useState<VexaOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [acceptingId, setAcceptingId] = useState<string | null>(null);

  const [drivers, setDrivers] = useState<OnlineDriver[]>([]);
  const [driversLoading, setDriversLoading] = useState(false);
  const [driversError, setDriversError] = useState('');

  const [assignmentOrder, setAssignmentOrder] = useState<VexaOrder | null>(null);
  const [selectedOrder, setSelectedOrder] = useState<VexaOrder | null>(null);
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

  const loadDriverLocations = useCallback(async (accessToken: string) => {
    setDriversLoading(true);
    setDriversError('');

    try {
      const data = await apiRequest(
        `/api/v1/dispatch/drivers/locations?city_code=${CITY_CODE}`,
        accessToken,
      );

      setDrivers(Array.isArray(data?.drivers) ? data.drivers : []);
    } catch (err) {
      setDriversError(
        err instanceof Error
          ? err.message
          : 'Не удалось загрузить водителей',
      );
    } finally {
      setDriversLoading(false);
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
    if (!savedToken) return;

    setToken(savedToken);

    Promise.all([
      loadProfile(savedToken),
      loadOrders(savedToken),
      loadDriverLocations(savedToken),
    ]).catch(() => {
      localStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setDispatcher(null);
    });
  }, [loadOrders, loadProfile, loadDriverLocations]);

  useEffect(() => {
    if (!token) return;

    const interval = window.setInterval(() => {
      loadOrders(token);
      loadDriverLocations(token);
    }, 15000);

    return () => window.clearInterval(interval);
  }, [token, loadOrders, loadDriverLocations]);

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

    await Promise.all([
      loadOrders(accessToken),
      loadDriverLocations(accessToken),
    ]);
  }

  function closeAssignment() {
    setAssignmentOrder(null);
    setAvailableDrivers([]);
    setSelectedDriver(null);
    setAssignmentError('');
    setLoadingDrivers(false);
    setAssigning(false);
  }

  async function openOrderFromFinance(orderId: string) {
    if (!token) {
      setError('Для просмотра карточки заказа необходимо войти в систему.');
      return;
    }

    setError('');

    try {
      const order = await apiRequest(
        `/api/v1/dispatch/orders/${encodeURIComponent(orderId)}?city_code=${CITY_CODE}`,
        token,
      );

      setSelectedOrder(order as VexaOrder);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Не удалось загрузить карточку заказа',
      );
    }
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setDispatcher(null);
    setOrders([]);
    setDrivers([]);
    setError('');
    setNotice('');
    setSelectedOrder(null);
    closeAssignment();
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

      setNotice(
        result.assigned
          ? `Заказ ${order.public_number}: водитель назначен автоматически.`
          : `Заказ ${order.public_number} принят. Свободных водителей нет — требуется ручное назначение.`,
      );

      await Promise.all([
        loadOrders(token),
        loadDriverLocations(token),
      ]);
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

      const list: AvailableDriver[] = Array.isArray(result?.drivers)
        ? result.drivers
        : [];

      setAvailableDrivers(list);

      if (list.length === 0) {
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

      await Promise.all([
        loadOrders(token),
        loadDriverLocations(token),
      ]);
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

  const newOrders = orders.filter(o => o.status === 'new');
  const acceptedOrders = orders.filter(o => o.status === 'accepted');

  const activeOrders = orders.filter(o =>
    ['assigned', 'arrived', 'in_progress'].includes(o.status),
  );

  const completedOrders = orders.filter(o => o.status === 'completed');
  const onlineDrivers = drivers.filter(d => d.is_online);
  const offlineDrivers = drivers.filter(d => !d.is_online);

  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <span className="mark">V</span>
          <b>VEXA</b>
          <small>DISPATCH</small>
        </div>

        <nav>
          <a
            href="#overview"
            className={activeSection === 'overview' ? 'active' : ''}
            onClick={() => setActiveSection('overview')}
          >
            <LayoutDashboard />Обзор
          </a>

          <a
            href="#map"
            className={activeSection === 'map' ? 'active' : ''}
            onClick={() => setActiveSection('map')}
          >
            <Map />Карта
          </a>

          <a
            href="#orders"
            className={activeSection === 'orders' ? 'active' : ''}
            onClick={() => setActiveSection('orders')}
          >
            <CarFront />Заказы
          </a>

          <a
            href="#drivers"
            className={activeSection === 'drivers' ? 'active' : ''}
            onClick={() => setActiveSection('drivers')}
          >
            <Users />Водители
          </a>

          <a
            href="#finance"
            className={activeSection === 'finance' ? 'active' : ''}
            onClick={event => {
              event.preventDefault();
              setActiveSection('finance');
            }}
          >
            <Wallet />Финансы
          </a>

          <a
            href="#settings"
            onClick={event => event.preventDefault()}
          >
            <Settings />Настройки
          </a>
        </nav>

        <div className="branch">
          <span className="dot" />
          Оболенск · Пилотный город
        </div>
      </aside>

      <main>
        <header id="overview">
          <div>
            <p className="eyebrow">ПАНЕЛЬ УПРАВЛЕНИЯ</p>
            <h1>Обзор диспетчера</h1>
            <p style={{
              color: '#8994a3',
              fontSize: 11,
              marginTop: 7,
            }}>
              {dispatcher?.username || 'Диспетчер'} · Оболенск
            </p>
          </div>

          <div className="headright">
            <span className="online"><i />Сервер подключён</span>

            <button
              onClick={() => {
                loadOrders(token);
                loadDriverLocations(token);
              }}
              title="Обновить данные"
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

        {activeSection === 'finance' ? (
          <>
            <FinanceSummaryPanel
              token={token}
              cityCode={CITY_CODE}
            />
            <DriverFinancePanel
              token={token}
              cityCode={CITY_CODE}
              onOpenOrder={openOrderFromFinance}
            />
          </>
        ) : (
          <>
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

            <section id="drivers" style={panelStyle}>
              <div style={panelHeaderStyle}>
                <div>
                  <h2 style={panelTitleStyle}>Водители на линии</h2>
                  <p style={mutedTextStyle}>

                    Последние сохранённые сведения о водителях · Оболенск
                  </p>
                </div>

                <button
                  onClick={() => loadDriverLocations(token)}
                  disabled={driversLoading}
                  style={secondaryButtonStyle}
                >
                  <RefreshCw
                    size={14}
                    style={{ marginRight: 6, verticalAlign: 'middle' }}
                  />
                  {driversLoading ? 'Обновление...' : 'Обновить'}
                </button>
              </div>

              <div style={driverStatsStyle}>
                <div style={driverStatCardStyle}>
                  <span style={statLabelStyle}>На линии</span>
                  <strong style={{
                    ...statNumberStyle,
                    color: '#07866f',
                  }}>
                    {onlineDrivers.length}
                  </strong>
                </div>

                <div style={driverStatCardStyle}>
                  <span style={statLabelStyle}>Не на линии</span>
                  <strong style={statNumberStyle}>
                    {offlineDrivers.length}
                  </strong>
                </div>

                <div style={driverStatCardStyle}>
                  <span style={statLabelStyle}>Всего водителей</span>
                  <strong style={statNumberStyle}>
                    {drivers.length}
                  </strong>
                </div>
              </div>

              {driversError && (
                <div style={errorStyle}>
                  <AlertCircle size={16} />
                  {driversError}
                </div>
              )}

              {driversLoading && drivers.length === 0 && (
                <p style={mutedTextStyle}>
                  Загрузка списка водителей...
                </p>
              )}

              {!driversLoading && drivers.length === 0 && !driversError && (
                <div style={emptyDriversStyle}>
                  <Users size={27} />
                  <p>В этом городе пока нет зарегистрированных водителей.</p>
                </div>
              )}

              {onlineDrivers.length > 0 && (
                <>
                  <h3 style={subheadingStyle}>
                    На линии ({onlineDrivers.length})
                  </h3>

                  <div style={onlineListStyle}>
                    {onlineDrivers.map(driver => (
                      <div
                        key={driver.user_id}
                        style={onlineDriverCardStyle}
                      >
                        <div style={onlineDriverTopStyle}>
                          <div style={driverAvatarStyle}>
                            <CarFront size={19} />
                          </div>

                          <div style={{ flex: 1, minWidth: 0 }}>
                            <b style={driverNameStyle}>
                              {driver.username}
                            </b>

                            <span style={driverPhoneStyle}>
                              {driver.phone || 'Телефон не указан'}
                            </span>
                          </div>

                          <span style={onlineBadgeStyle}>
                            <i />
                            На линии
                          </span>
                        </div>

                        <div style={driverMetaStyle}>
                          <span>
                            Рейтинг: ★ {Number(driver.rating || 0).toFixed(1)}
                          </span>
                          <span>Город: {driver.city?.name || '—'}</span>
                          <span>Филиал: {driver.branch?.name || 'Не указан'}</span>
                        </div>

                        <div style={locationInfoStyle}>
                          <MapPin size={15} />

                          {driver.location ? (
                            <div>
                              <b>
                                {Number(driver.location.latitude).toFixed(5)},{' '}
                                {Number(driver.location.longitude).toFixed(5)}
                              </b>

                              <small>
                                Последние координаты: {formatDate(
                                  driver.location.recorded_at ||
                                  driver.location.updated_at,
                                )}

                                {driver.location.accuracy_meters != null
                                  ? ` · точность ±${Math.round(driver.location.accuracy_meters)} м`
                                  : ''}
                              </small>
                            </div>
                          ) : (
                            <div>
                              <b>Координаты не получены</b>
                              <small>Последнее местоположение пока неизвестно</small>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {offlineDrivers.length > 0 && (
                <details style={{ marginTop: 14 }}>
                  <summary style={offlineSummaryStyle}>
                    Не на линии ({offlineDrivers.length})
                  </summary>

                  <div style={onlineListStyle}>
                    {offlineDrivers.map(driver => (
                      <div
                        key={driver.user_id}
                        style={{
                          ...onlineDriverCardStyle,
                          opacity: 0.72,
                        }}
                      >
                        <div style={onlineDriverTopStyle}>
                          <div style={{
                            ...driverAvatarStyle,
                            background: '#f0f2f5',
                            color: '#8994a3',
                          }}>
                            <CarFront size={19} />
                          </div>

                          <div style={{ flex: 1, minWidth: 0 }}>
                            <b style={driverNameStyle}>
                              {driver.username}
                            </b>

                            <span style={driverPhoneStyle}>
                              {driver.phone || 'Телефон не указан'}
                            </span>
                          </div>

                          <span style={offlineBadgeStyle}>
                            Не на линии
                          </span>
                        </div>

                        <div style={driverMetaStyle}>
                          <span>Город: {driver.city?.name || '—'}</span>
                          <span>Филиал: {driver.branch?.name || 'Не указан'}</span>
                        </div>

                        <div style={locationInfoStyle}>
                          <MapPin size={15} />

                          {driver.location ? (
                            <div>
                              <b>
                                {Number(driver.location.latitude).toFixed(5)},{' '}
                                {Number(driver.location.longitude).toFixed(5)}
                              </b>

                              <small>
                                Последние сохранённые координаты: {formatDate(
                                  driver.location.recorded_at ||
                                  driver.location.updated_at,
                                )}
                              </small>
                            </div>
                          ) : (
                            <div>
                              <b>Координаты не получены</b>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              )}

              <p style={gpsNoticeStyle}>
                <Radio size={13} />
                Панель показывает последние сохранённые координаты. Сам факт
                нахождения водителя на линии не означает непрерывную передачу GPS.
              </p>
            </section>

            <section className="content">
              <article id="map" className="mapcard">
                <div className="cardhead">
                  <div>
                    <h2>Карта города</h2>
                    <p>Карта 2ГИС · Местоположение водителей</p>
                  </div>

                  <span className="live">
                    <i />
                    ОБОЛЕНСК
                  </span>
                </div>

                <div className="maparea" style={{
                  padding: 0,
                  minHeight: 300,
                }}>
                  <VexaMap
                    drivers={drivers}
                    height={430}
                  />
                </div>
              </article>

              <article id="orders" className="orders">
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
                  <p style={mutedTextStyle}>Загрузка заказов...</p>
                )}

                {!loading && orders.length === 0 && (
                  <p style={mutedTextStyle}>Заказов пока нет.</p>
                )}

                {orders.map(order => (
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
                        {order.customer_phone ? ` · ${order.customer_phone}` : ''}
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
                <b>Обновление данных</b>
                <span>
                  Заказы и список водителей автоматически обновляются каждые 15 секунд.
                </span>
              </div>
            </section>
          </>
        )}
      </main>

      {selectedOrder && (
        <div
          style={modalOverlayStyle}
          onClick={() => setSelectedOrder(null)}
        >
          <div
            style={modalStyle}
            onClick={event => event.stopPropagation()}
          >
            <div style={modalHeaderStyle}>
              <div>
                <h2 style={{ margin: 0, fontSize: 18 }}>
                  Карточка заказа
                </h2>

                <p style={{
                  margin: '6px 0 0',
                  color: '#8994a3',
                  fontSize: 12,
                }}>
                  Заказ №{selectedOrder.public_number}
                </p>
              </div>

              <button
                onClick={() => setSelectedOrder(null)}
                style={iconButtonStyle}
                title="Закрыть карточку заказа"
              >
                <X size={20} />
              </button>
            </div>

            <div style={{
              display: 'grid',
              gap: 13,
              marginTop: 20,
            }}>
              <div>
                <span style={orderDetailLabelStyle}>Статус заказа</span>
                <span
                  className={`status ${getStatusClass(selectedOrder.status)}`}
                  style={{
                    display: 'inline-block',
                    width: 'fit-content',
                    marginTop: 5,
                  }}
                >

                  {getStatusLabel(selectedOrder.status)}
                </span>
              </div>

              <div style={modalDividerStyle} />

              <div>
                <span style={orderDetailLabelStyle}>Клиент</span>
                <b style={orderDetailValueStyle}>
                  {selectedOrder.customer_name || 'Анонимный заказ'}
                </b>
                {selectedOrder.customer_phone && (
                  <span style={orderDetailSecondaryStyle}>
                    {selectedOrder.customer_phone}
                  </span>
                )}
              </div>

              <div>
                <span style={orderDetailLabelStyle}>Откуда</span>
                <b style={orderDetailValueStyle}>
                  {selectedOrder.pickup_address}
                </b>
              </div>

              <div>
                <span style={orderDetailLabelStyle}>Куда</span>
                <b style={orderDetailValueStyle}>
                  {selectedOrder.destination_address}
                </b>
              </div>

              <div style={modalDividerStyle} />

              <div style={orderDetailGridStyle}>
                <div>
                  <span style={orderDetailLabelStyle}>Стоимость</span>
                  <b style={orderDetailValueStyle}>
                    {Number(selectedOrder.price_rub || 0).toLocaleString('ru-RU')} ₽
                  </b>
                </div>

                <div>
                  <span style={orderDetailLabelStyle}>Способ оплаты</span>
                  <b style={orderDetailValueStyle}>
                    {getPaymentLabel(selectedOrder.payment_method)}
                  </b>
                </div>

                <div>
                  <span style={orderDetailLabelStyle}>Дата создания</span>
                  <b style={orderDetailValueStyle}>
                    {formatDate(selectedOrder.created_at)}
                  </b>
                </div>

                <div>
                  <span style={orderDetailLabelStyle}>Город</span>
                  <b style={orderDetailValueStyle}>
                    {selectedOrder.city_code}
                  </b>
                </div>
              </div>

              <div style={modalDividerStyle} />

              <section style={{ display: 'grid', gap: 12 }}>
                <div>
                  <span style={orderDetailLabelStyle}>Хронология событий</span>
                  <p style={{
                    margin: '5px 0 0',
                    color: '#8994a3',
                    fontSize: 11,
                    lineHeight: 1.5,
                  }}>
                    История создания заказа, изменения статусов и предложений водителям.
                  </p>
                </div>

                {Array.isArray(selectedOrder.timeline) && selectedOrder.timeline.length > 0 ? (
                  <div style={{ display: 'grid', gap: 0 }}>
                    {selectedOrder.timeline.map((event, index) => (
                      <div
                        key={event.event_id}
                        style={{
                          display: 'grid',
                          gridTemplateColumns: '14px minmax(0, 1fr)',
                          columnGap: 10,
                        }}
                      >
                        <div style={{
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                        }}>
                          <span style={{
                            width: 9,
                            height: 9,
                            marginTop: 4,
                            borderRadius: '50%',
                            background: event.event_type === 'order_status'
                              ? '#0f9f91'
                              : event.event_type === 'order_created'
                                ? '#64748b'
                                : '#3b82f6',
                            flexShrink: 0,
                          }} />
                          {index < selectedOrder.timeline!.length - 1 && (
                            <span style={{
                              width: 1,
                              flex: 1,
                              minHeight: 28,
                              background: '#e2e8f0',
                              marginTop: 4,
                            }} />
                          )}
                        </div>

                        <div style={{
                          display: 'grid',
                          gap: 3,
                          paddingBottom: index < selectedOrder.timeline!.length - 1 ? 15 : 0,
                          minWidth: 0,
                        }}>
                          <b style={{
                            color: '#172033',
                            fontSize: 12,
                            lineHeight: 1.4,
                          }}>
                            {event.title}
                          </b>
                          <span style={{
                            color: '#8994a3',
                            fontSize: 10,
                          }}>
                            {formatDate(event.occurred_at)}
                          </span>
                          {event.description && (
                            <span style={{
                              color: '#526174',
                              fontSize: 11,
                              lineHeight: 1.5,
                              overflowWrap: 'anywhere',
                            }}>
                              {event.description}
                            </span>
                          )}
                          {event.actor && (
                            <span style={{
                              color: '#64748b',
                              fontSize: 10,
                            }}>
                              Участник: {event.actor}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={{
                    margin: 0,
                    padding: '12px',
                    borderRadius: 10,
                    background: '#f8fafc',
                    color: '#8994a3',
                    fontSize: 11,
                  }}>
                    События пока не записаны.
                  </p>
                )}
              </section>

              <div style={modalDividerStyle} />

              <span style={orderDetailSecondaryStyle}>
                ID заказа: {selectedOrder.id}
              </span>
            </div>

            <div style={modalActionsStyle}>
              <button
                onClick={() => setSelectedOrder(null)}
                style={secondaryButtonStyle}
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}

      {assignmentOrder && (
        <div style={modalOverlayStyle}>
          <div style={modalStyle}>
            <div style={modalHeaderStyle}>
              <div>
                <h2 style={{ margin: 0, fontSize: 18 }}>
                  Назначение водителя
                </h2>

                <p style={{
                  margin: '6px 0 0',
                  color: '#8994a3',
                  fontSize: 12,
                }}>
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

            <div style={{
              margin: '16px 0',
              fontSize: 12,
              color: '#526174',
            }}>
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
              <p style={mutedTextStyle}>
                Загружаем список водителей...
              </p>
            )}

            {!loadingDrivers && availableDrivers.length === 0 && (
              <div style={emptyDriversStyle}>
                <Users size={25} />
                <p>Подходящих свободных водителей пока нет.</p>
              </div>
            )}

            {availableDrivers.length > 0 && (
              <div style={driverListStyle}>
                {availableDrivers.map(driver => {
                  const selected =
                    selectedDriver?.driver_user_id === driver.driver_user_id &&
                    selectedDriver?.vehicle.id === driver.vehicle.id;

                  return (
                    <button
                      key={`${driver.driver_user_id}-${driver.vehicle.id}`}
                      onClick={() => setSelectedDriver(driver)}
                      style={{
                        ...driverCardStyle,
                        border: selected
                          ? '2px solid #20b8aa'
                          : '1px solid #e4eaf0',
                        background: selected ? '#effbf9' : '#fff',
                      }}
                    >
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                      }}>
                        <div style={driverAvatarStyle}>
                          <CarFront size={19} />
                        </div>

                        <div style={{ flex: 1, textAlign: 'left' }}>
                          <b style={{
                            display: 'block',
                            fontSize: 13,
                            color: '#172033',
                          }}>
                            {driver.username}
                          </b>

                          <span style={{
                            fontSize: 11,
                            color: '#8994a3',
                          }}>
                            {driver.phone || 'Телефон не указан'}
                          </span>
                        </div>

                        <span style={ratingStyle}>
                          ★ {Number(driver.rating || 0).toFixed(1)}
                        </span>
                      </div>

                      <div style={vehicleInfoStyle}>
                        <b>
                          {[
                            driver.vehicle.make,
                            driver.vehicle.model,
                          ].filter(Boolean).join(' ') || 'Автомобиль'}
                        </b>

                        <span>
                          {[
                            driver.vehicle.color,
                            driver.vehicle.license_plate,
                          ].filter(Boolean).join(' · ')}
                        </span>
                      </div>

                      {driver.location && (
                        <small style={{
                          display: 'block',
                          color: '#8994a3',
                          marginTop: 7,
                        }}>
                          GPS: {Number(driver.location.latitude).toFixed(5)},
                          {' '}
                          {Number(driver.location.longitude).toFixed(5)}
                        </small>
                      )}

                      {selected && (
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
                  cursor: !selectedDriver || assigning
                    ? 'not-allowed'
                    : 'pointer',
                }}
              >
                {assigning
                  ? 'Назначаем...'
                  : 'Подтвердить назначение'}
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

const panelStyle: React.CSSProperties = {
  background: '#fff',
  border: '1px solid #e8edf2',
  borderRadius: 14,
  padding: 20,
  marginBottom: 20,
};

const panelHeaderStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  gap: 12,
  flexWrap: 'wrap',
};

const panelTitleStyle: React.CSSProperties = {
  margin: 0,
  fontSize: 17,
  color: '#172033',
};

const mutedTextStyle: React.CSSProperties = {
  color: '#8994a3',
  fontSize: 12,
};

const driverStatsStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
  gap: 10,
  margin: '17px 0',
};

const driverStatCardStyle: React.CSSProperties = {
  background: '#f7f9fb',
  borderRadius: 10,
  padding: 13,
  display: 'grid',
  gap: 5,
};

const statLabelStyle: React.CSSProperties = {
  fontSize: 11,
  color: '#8994a3',
};

const statNumberStyle: React.CSSProperties = {
  fontSize: 24,
  color: '#172033',
};

const subheadingStyle: React.CSSProperties = {
  fontSize: 13,
  color: '#344054',
  margin: '18px 0 10px',
};

const onlineListStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
  gap: 10,
};

const onlineDriverCardStyle: React.CSSProperties = {
  border: '1px solid #e8edf2',
  borderRadius: 11,
  padding: 13,
  background: '#fff',
  minWidth: 0,
};

const onlineDriverTopStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 9,
};

const driverAvatarStyle: React.CSSProperties = {
  width: 36,
  height: 36,
  flexShrink: 0,
  borderRadius: 9,
  background: '#e7f8f6',
  color: '#159b8f',
  display: 'grid',
  placeItems: 'center',
};

const driverNameStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 13,
  color: '#172033',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
};

const driverPhoneStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 11,
  color: '#8994a3',
  marginTop: 3,
};

const onlineBadgeStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 5,
  color: '#07866f',
  background: '#e8f8f4',
  borderRadius: 20,
  padding: '5px 8px',
  fontSize: 10,
  fontWeight: 700,
  whiteSpace: 'nowrap',
};

const offlineBadgeStyle: React.CSSProperties = {
  color: '#667085',
  background: '#f0f2f5',
  borderRadius: 20,
  padding: '5px 8px',
  fontSize: 10,
  whiteSpace: 'nowrap',
};

const driverMetaStyle: React.CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: '6px 12px',
  color: '#667085',
  fontSize: 10,
  marginTop: 12,
};

const locationInfoStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'flex-start',
  gap: 7,
  borderTop: '1px solid #edf0f3',
  marginTop: 11,
  paddingTop: 10,
  color: '#159b8f',
  fontSize: 11,
};

const gpsNoticeStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  color: '#8994a3',
  fontSize: 10,
  lineHeight: 1.5,
  marginTop: 16,
};

const offlineSummaryStyle: React.CSSProperties = {
  cursor: 'pointer',
  color: '#667085',
  fontSize: 12,
  fontWeight: 600,
  padding: '8px 0',
};

const emptyDriversStyle: React.CSSProperties = {
  padding: 25,
  textAlign: 'center',
  color: '#8994a3',
  background: '#f7f9fb',
  borderRadius: 10,
  fontSize: 12,
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

const modalActionsStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'flex-end',
  gap: 9,
  marginTop: 20,
  paddingTop: 15,
  borderTop: '1px solid #edf0f3',
};

const orderDetailLabelStyle: React.CSSProperties = {
  display: 'block',
  color: '#8994a3',
  fontSize: 11,
  marginBottom: 4,
};

const orderDetailValueStyle: React.CSSProperties = {
  display: 'block',
  color: '#172033',
  fontSize: 13,
  lineHeight: 1.5,
  overflowWrap: 'anywhere',
};

const orderDetailSecondaryStyle: React.CSSProperties = {
  display: 'block',
  color: '#8994a3',
  fontSize: 11,
  marginTop: 4,
  overflowWrap: 'anywhere',
};

const orderDetailGridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
  gap: 14,
};

createRoot(document.getElementById('root')!).render(<App />);
