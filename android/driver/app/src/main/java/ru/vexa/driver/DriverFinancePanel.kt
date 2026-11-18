
import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  ChevronDown,
  ChevronUp,
  History,
  RefreshCw,
} from 'lucide-react';

type FinanceDriver = {
  driver_user_id: string;
  username: string;
  phone?: string | null;
  rating: string;
  is_online: boolean;
  city_code: string;
  city_name: string;
  branch_name?: string | null;
  balance_kopecks: number;
  balance_rub: number;
  reserved_kopecks: number;
  available_kopecks: number;
};

type FinanceResponse = {
  city_code: string;
  drivers_count: number;
  drivers: FinanceDriver[];
};

type FinanceTransaction = {
  id: string;
  transaction_type: string;
  payment_method?: string | null;
  amount_kopecks: number;
  balance_change_kopecks: number;
  balance_after_kopecks: number;
  reserved_after_kopecks: number;
  description?: string | null;
  order_id?: string | null;
  order_public_number?: string | null;
  created_at: string;
};

type FinanceHistoryResponse = {
  driver: {
    user_id: string;
    username: string;
    phone?: string | null;
    city_code: string;
    city_name: string;
    branch_name?: string | null;
  };
  current_balance_kopecks: number;
  reserved_kopecks: number;
  available_kopecks: number;
  total_transactions: number;
  limit: number;
  offset: number;
  transactions: FinanceTransaction[];
};

type Props = {
  token: string;
  cityCode: string;
};

const API_BASE = 'https://109.120.184.20';
const HISTORY_PAGE_SIZE = 30;

const money = (kopecks: number) =>
  `${(kopecks / 100).toLocaleString('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ₽`;

const secondaryButtonStyle: React.CSSProperties = {
  border: '1px solid #dfe6eb',
  borderRadius: 8,
  background: '#fff',
  color: '#526174',
  padding: '10px 13px',
  fontSize: 12,
  fontWeight: 600,
  cursor: 'pointer',
};

const mutedStyle: React.CSSProperties = {
  color: '#8994a3',
  fontSize: 12,
};

const cardStyle: React.CSSProperties = {
  border: '1px solid #e8edf2',
  borderRadius: 11,
  padding: 14,
  background: '#fff',
};

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return 'Дата не указана';
  }

  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function transactionTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    trip_commission: 'Комиссия за поездку',
    commission: 'Комиссия за поездку',
    completed_trip: 'Расчёт по завершённой поездке',
    payout: 'Выплата водителю',
    payout_reserve: 'Резервирование выплаты',
    payout_release: 'Отмена резерва выплаты',
    adjustment: 'Корректировка баланса',
    refund: 'Возврат средств',
  };

  return labels[type] || 'Операция по кошельку';
}

function paymentMethodLabel(method?: string | null): string {
  const labels: Record<string, string> = {
    cash: 'Наличные',
    driver_transfer: 'Перевод водителю',
    card: 'Банковская карта',
    sbp: 'СБП',
  };

  return method ? labels[method] || method : '—';
}

async function financeRequest(
  path: string,
  token: string,
  options: RequestInit = {},
) {
  const headers = new Headers(options.headers || {});
  headers.set('Content-Type', 'application/json');
  headers.set('Authorization', `Bearer ${token}`);

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

export default function DriverFinancePanel({
  token,
  cityCode,
}: Props) {
  const [drivers, setDrivers] = useState<FinanceDriver[]>([]);
  const [loading, setLoading] = useState(false);
  const [historyDriverId, setHistoryDriverId] = useState('');
  const [history, setHistory] = useState<FinanceHistoryResponse | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [historyOffset, setHistoryOffset] = useState(0);
  const [error, setError] = useState('');

  const loadFinance = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    setError('');

    try {
      const data: FinanceResponse = await financeRequest(
        `/api/v1/dispatch/drivers/finance?city_code=${encodeURIComponent(cityCode)}`,
        token,
      );

      setDrivers(Array.isArray(data?.drivers) ? data.drivers : []);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Не удалось загрузить финансовые данные',
      );
    } finally {
      setLoading(false);
    }
  }, [token, cityCode]);

  const loadHistory = useCallback(async (
    driverId: string,
    offset = 0,
  ) => {
    if (!token || !driverId) return;

    setHistoryLoading(true);
    setHistoryError('');

    try {
      const data: FinanceHistoryResponse = await financeRequest(
        `/api/v1/dispatch/drivers/${encodeURIComponent(driverId)}/finance/transactions` +
        `?city_code=${encodeURIComponent(cityCode)}` +
        `&limit=${HISTORY_PAGE_SIZE}&offset=${offset}`,
        token,
      );

      setHistory(data);
      setHistoryOffset(offset);
    } catch (err) {
      setHistoryError(
        err instanceof Error
          ? err.message
          : 'Не удалось загрузить историю операций',
      );
    } finally {
      setHistoryLoading(false);
    }
  }, [token, cityCode]);

  useEffect(() => {
    loadFinance();
  }, [loadFinance]);

  function toggleHistory(driverId: string) {
    if (historyDriverId === driverId) {
      setHistoryDriverId('');
      setHistory(null);
      setHistoryError('');
      return;
    }

    setHistoryDriverId(driverId);
    setHistory(null);
    loadHistory(driverId, 0);
  }

  const totalBalance = drivers.reduce(
    (sum, driver) => sum + Number(driver.balance_kopecks || 0),
    0,
  );

  const negativeBalanceDrivers = drivers.filter(
    driver => Number(driver.balance_kopecks || 0) < 0,
  );

  return (
    <section style={{
      display: 'grid',
      gap: 18,
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12,
      }}>
        <div>
          <h2 style={{
            margin: 0,
            fontSize: 19,
            color: '#172033',
          }}>
            Финансы водителей
          </h2>

          <p style={{
            ...mutedStyle,
            margin: '6px 0 0',
          }}>
            Балансы кошельков и история финансовых операций
          </p>
        </div>

        <button
          type="button"
          onClick={loadFinance}
          disabled={loading}
          style={{
            ...secondaryButtonStyle,
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            opacity: loading ? 0.6 : 1,
          }}
        >
          <RefreshCw size={15} />
          {loading ? 'Обновление...' : 'Обновить'}
        </button>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: 12,
      }}>
        <div style={{
          ...cardStyle,
          background: '#f7f9fb',
        }}>
          <span style={mutedStyle}>
            Суммарный баланс кошельков
          </span>

          <strong style={{
            display: 'block',
            fontSize: 25,
            color: totalBalance < 0 ? '#b54708' : '#087e70',
            marginTop: 8,
          }}>
            {money(totalBalance)}
          </strong>
        </div>

        <div style={{
          ...cardStyle,
          background: '#f7f9fb',
        }}>
          <span style={mutedStyle}>
            Водителей с отрицательным балансом
          </span>

          <strong style={{
            display: 'block',
            fontSize: 25,
            color: '#b54708',
            marginTop: 8,
          }}>
            {negativeBalanceDrivers.length}
          </strong>
        </div>

        <div style={{
          ...cardStyle,
          background: '#f7f9fb',
        }}>
          <span style={mutedStyle}>
            Активных водителей в списке
          </span>

          <strong style={{
            display: 'block',
            fontSize: 25,
            color: '#172033',
            marginTop: 8,
          }}>
            {drivers.length}
          </strong>
        </div>
      </div>

      {error && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: '#b42318',
          background: '#fff0ee',
          borderRadius: 8,
          padding: 11,
          fontSize: 12,
        }}>
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <div style={cardStyle}>
        <h3 style={{
          margin: '0 0 12px',
          fontSize: 15,
          color: '#172033',
        }}>
          Кошельки водителей и история операций
        </h3>

        {loading && drivers.length === 0 && (
          <p style={mutedStyle}>Загружаем финансовые данные...</p>
        )}

        {!loading && drivers.length === 0 && !error && (
          <p style={mutedStyle}>Активных водителей пока нет.</p>
        )}

        {drivers.length > 0 && (
          <div style={{
            display: 'grid',
            gap: 8,
          }}>
            {drivers.map(driver => {
              const isHistoryOpen = historyDriverId === driver.driver_user_id;
              const balance = Number(driver.balance_kopecks || 0);
              const reserved = Number(driver.reserved_kopecks || 0);
              const available = Number(driver.available_kopecks || 0);

              return (
                <div
                  key={driver.driver_user_id}
                  style={{
                    borderBottom: '1px solid #edf0f3',
                    padding: '11px 0',
                  }}
                >
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                    flexWrap: 'wrap',
                  }}>
                    <div style={{
                      display: 'grid',
                      gap: 4,
                    }}>
                      <b style={{
                        color: '#172033',
                        fontSize: 13,
                      }}>
                        {driver.username}
                      </b>

                      <span style={mutedStyle}>
                        {driver.branch_name || 'Без филиала'}
                        {' · '}
                        {driver.is_online ? 'На линии' : 'Не на линии'}
                        {' · '}
                        Рейтинг: {driver.rating}
                      </span>
                    </div>

                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      flexWrap: 'wrap',
                    }}>
                      <div style={{
                        display: 'grid',
                        gap: 3,
                        textAlign: 'right',
                      }}>
                        <strong style={{
                          color: balance < 0 ? '#b54708' : '#087e70',
                          fontSize: 15,
                        }}>
                          {money(balance)}
                        </strong>
                        <span style={mutedStyle}>
                          {balance < 0 ? 'Отрицательный баланс' : 'Баланс кошелька'}
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={() => toggleHistory(driver.driver_user_id)}
                        style={{
                          ...secondaryButtonStyle,
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          padding: '8px 10px',
                        }}
                      >
                        <History size={14} />
                        История
                        {isHistoryOpen
                          ? <ChevronUp size={14} />
                          : <ChevronDown size={14} />}
                      </button>
                    </div>
                  </div>

                  <div style={{
                    display: 'flex',
                    gap: 16,
                    flexWrap: 'wrap',
                    marginTop: 8,
                    color: '#526174',
                    fontSize: 11,
                  }}>
                    <span>Доступно: {money(available)}</span>
                    <span>В резерве: {money(reserved)}</span>
                    {driver.phone && <span>Телефон: {driver.phone}</span>}
                  </div>

                  {isHistoryOpen && (
                    <div style={{
                      marginTop: 12,
                      padding: 12,
                      borderRadius: 9,
                      background: '#f7f9fb',
                      display: 'grid',
                      gap: 12,
                    }}>
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: 10,
                        flexWrap: 'wrap',
                      }}>
                        <div>
                          <b style={{
                            fontSize: 13,
                            color: '#172033',
                          }}>
                            История операций кошелька
                          </b>

                          {history && (
                            <p style={{
                              ...mutedStyle,
                              margin: '4px 0 0',
                            }}>
                              Всего записей: {history.total_transactions}
                              {' · '}
                              Текущий баланс: {money(history.current_balance_kopecks)}
                            </p>
                          )}
                        </div>

                        <button
                          type="button"
                          onClick={() => loadHistory(driver.driver_user_id, 0)}
                          disabled={historyLoading}
                          style={secondaryButtonStyle}
                        >
                          <RefreshCw size={13} />
                          {' '}Обновить
                        </button>
                      </div>

                      {historyLoading && (
                        <p style={mutedStyle}>Загружаем историю операций...</p>
                      )}

                      {historyError && (
                        <div style={{
                          color: '#b42318',
                          background: '#fff0ee',
                          borderRadius: 8,
                          padding: 10,
                          fontSize: 12,
                        }}>
                          {historyError}
                        </div>
                      )}

                      {!historyLoading && !historyError &&
                        history && history.transactions.length === 0 && (
                          <p style={mutedStyle}>
                            У этого водителя пока нет операций по кошельку.
                          </p>
                        )}

                      {history && history.transactions.length > 0 && (
                        <>
                          <div style={{
                            display: 'grid',
                            gap: 9,
                          }}>
                            {history.transactions.map(transaction => {
                              const change = Number(
                                transaction.balance_change_kopecks ??
                                transaction.amount_kopecks ??
                                0,
                              );

                              return (
                                <div
                                  key={transaction.id}
                                  style={{
                                    background: '#fff',
                                    border: '1px solid #e8edf2',
                                    borderRadius: 8,
                                    padding: 11,
                                    display: 'grid',
                                    gap: 7,
                                  }}
                                >
                                  <div style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'flex-start',
                                    gap: 10,
                                    flexWrap: 'wrap',
                                  }}>
                                    <div style={{
                                      display: 'grid',
                                      gap: 4,
                                    }}>
                                      <b style={{
                                        color: '#172033',
                                        fontSize: 12,
                                      }}>
                                        {transactionTypeLabel(transaction.transaction_type)}
                                      </b>

                                      <span style={mutedStyle}>
                                        {formatDate(transaction.created_at)}
                                      </span>
                                    </div>

                                    <strong style={{
                                      color: change < 0 ? '#b54708' : '#087e70',
                                      fontSize: 13,
                                    }}>
                                      {change < 0 ? '−' : '+'}
                                      {money(Math.abs(change))}
                                    </strong>
                                  </div>

                                  <div style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    gap: 8,
                                    flexWrap: 'wrap',
                                    color: '#526174',
                                    fontSize: 11,
                                  }}>
                                    <span>
                                      Способ: {paymentMethodLabel(transaction.payment_method)}
                                    </span>

                                    <b style={{
                                      color: transaction.balance_after_kopecks < 0
                                        ? '#b54708'
                                        : '#172033',
                                    }}>
                                      Баланс после операции: {money(transaction.balance_after_kopecks)}
                                    </b>
                                  </div>

                                  {transaction.order_public_number && (
                                    <span style={{
                                      color: '#526174',
                                      fontSize: 11,
                                    }}>
                                      Заказ № {transaction.order_public_number}
                                    </span>
                                  )}
                                </div>
                              );
                            })}
                          </div>

                          <div style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            gap: 10,
                            flexWrap: 'wrap',
                          }}>
                            <span style={mutedStyle}>
                              Показано {historyOffset + 1}–
                              {historyOffset + history.transactions.length}
                              {' '}из {history.total_transactions}
                            </span>

                            <div style={{
                              display: 'flex',
                              gap: 8,
                            }}>
                              <button
                                type="button"
                                disabled={historyOffset === 0 || historyLoading}
                                onClick={() => loadHistory(
                                  driver.driver_user_id,
                                  Math.max(0, historyOffset - HISTORY_PAGE_SIZE),
                                )}
                                style={{
                                  ...secondaryButtonStyle,
                                  opacity: historyOffset === 0 ? 0.5 : 1,
                                }}
                              >
                                Назад
                              </button>

                              <button
                                type="button"
                                disabled={
                                  historyOffset + history.transactions.length >=
                                    history.total_transactions ||
                                  historyLoading
                                }
                                onClick={() => loadHistory(
                                  driver.driver_user_id,
                                  historyOffset + HISTORY_PAGE_SIZE,
                                )}
                                style={{
                                  ...secondaryButtonStyle,
                                  opacity:
                                    historyOffset + history.transactions.length >=
                                    history.total_transactions ? 0.5 : 1,
                                }}
                              >
                                Далее
                              </button>
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <p style={{
        ...mutedStyle,
        lineHeight: 1.5,
        margin: 0,
      }}>
        Баланс и история загружаются из кошелька водителя.
        Отрицательное значение отражает задолженность перед VEXA.
        Ручная регистрация погашения через диспетчерскую не используется.
      </p>
    </section>
  );
}
