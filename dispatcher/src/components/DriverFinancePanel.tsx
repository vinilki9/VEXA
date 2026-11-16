
import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Wallet,
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
  cash_debt_kopecks: number;
  cash_debt_rub: number;
};

type FinanceResponse = {
  city_code: string;
  drivers_count: number;
  total_cash_debt_kopecks: number;
  drivers: FinanceDriver[];
};

type RepaymentResponse = {
  success: boolean;
  message: string;
  paid_kopecks: number;
  remaining_debt_kopecks: number;
};

type Props = {
  token: string;
  cityCode: string;
};

const API_BASE = 'https://109.120.184.20';

const money = (kopecks: number) =>
  `${(kopecks / 100).toLocaleString('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ₽`;

const inputStyle: React.CSSProperties = {
  width: '100%',
  height: 43,
  boxSizing: 'border-box',
  border: '1px solid #dfe6eb',
  borderRadius: 8,
  padding: '0 12px',
  fontSize: 13,
  outline: 'none',
  background: '#fff',
  color: '#172033',
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

function parseRublesToKopecks(value: string): number | null {
  const normalized = value.trim().replace(',', '.');

  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) {
    return null;
  }

  const [rubles, fraction = ''] = normalized.split('.');
  const kopecks = Number(rubles) * 100 + Number(fraction.padEnd(2, '0'));

  if (
    !Number.isSafeInteger(kopecks) ||
    kopecks <= 0 ||
    kopecks > 2147483647
  ) {
    return null;
  }

  return kopecks;
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
  const [totalDebt, setTotalDebt] = useState(0);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [selectedDriverId, setSelectedDriverId] = useState('');
  const [amount, setAmount] = useState('');
  const [paymentMethod, setPaymentMethod] = useState<
    'cash' | 'driver_transfer'
  >('cash');

  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const loadFinance = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    setError('');

    try {
      const data: FinanceResponse = await financeRequest(
        `/api/v1/dispatch/drivers/finance?city_code=${encodeURIComponent(cityCode)}`,
        token,
      );

      setDrivers(
        Array.isArray(data?.drivers)
          ? data.drivers
          : [],
      );

      setTotalDebt(
        Number(data?.total_cash_debt_kopecks || 0),
      );
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

  useEffect(() => {
    loadFinance();
  }, [loadFinance]);

  const selectedDriver = drivers.find(
    driver => driver.driver_user_id === selectedDriverId,
  );

  async function submitRepayment(event: React.FormEvent) {
    event.preventDefault();

    if (!selectedDriver || submitting) return;

    setError('');
    setNotice('');

    const amountKopecks = parseRublesToKopecks(amount);

    if (amountKopecks === null) {
      setError('Введите корректную сумму в рублях.');
      return;
    }

    if (amountKopecks > selectedDriver.cash_debt_kopecks) {
      setError('Сумма превышает текущую задолженность водителя.');
      return;
    }

    const confirmed = window.confirm(
      `Зарегистрировать погашение ${money(amountKopecks)}?\n` +
      `Водитель: ${selectedDriver.username}\n` +
      `Способ: ${
        paymentMethod === 'cash'
          ? 'Наличные'
          : 'Перевод водителю'
      }`,
    );

    if (!confirmed) return;

    setSubmitting(true);

    try {
      const result: RepaymentResponse = await financeRequest(
        `/api/v1/dispatch/drivers/${selectedDriver.driver_user_id}/finance/repayments`,
        token,
        {
          method: 'POST',
          body: JSON.stringify({
            amount_kopecks: amountKopecks,
            payment_method: paymentMethod,
          }),
        },
      );

      setNotice(
        `Погашение зарегистрировано. Оплачено: ` +
        `${money(result.paid_kopecks)}. Остаток долга: ` +
        `${money(result.remaining_debt_kopecks)}.`,
      );

      setAmount('');
      await loadFinance();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Не удалось зарегистрировать погашение',
      );
    } finally {
      setSubmitting(false);
    }
  }

  const indebtedDrivers = drivers.filter(
    driver => driver.cash_debt_kopecks > 0,
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
            Задолженность по наличным поездкам и её погашение
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
            Общая задолженность водителей
          </span>

          <strong style={{
            display: 'block',
            fontSize: 25,
            color: '#172033',
            marginTop: 8,
          }}>
            {money(totalDebt)}
          </strong>
        </div>

        <div style={{
          ...cardStyle,
          background: '#f7f9fb',
        }}>
          <span style={mutedStyle}>
            Водителей с задолженностью
          </span>

          <strong style={{
            display: 'block',
            fontSize: 25,
            color: '#172033',
            marginTop: 8,
          }}>
            {indebtedDrivers.length}
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

      {notice && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: '#087e70',
          background: '#e8f8f4',
          borderRadius: 8,
          padding: 11,
          fontSize: 12,
        }}>
          <CheckCircle2 size={16} />
          {notice}
        </div>
      )}

      <div style={cardStyle}>
        <h3 style={{
          margin: '0 0 13px',
          fontSize: 15,
          color: '#172033',
        }}>
          Регистрация погашения задолженности
        </h3>

        <form
          onSubmit={submitRepayment}
          style={{
            display: 'grid',
            gap: 13,
          }}
        >
          <label style={{
            display: 'grid',
            gap: 6,
            color: '#526174',
            fontSize: 12,
            fontWeight: 600,
          }}>
            Водитель

            <select
              value={selectedDriverId}
              onChange={event => {
                setSelectedDriverId(event.target.value);
                setAmount('');
                setNotice('');
              }}
              required
              style={inputStyle}
            >
              <option value="">Выберите водителя</option>

              {indebtedDrivers.map(driver => (
                <option
                  key={driver.driver_user_id}
                  value={driver.driver_user_id}
                >
                  {driver.username} — {money(driver.cash_debt_kopecks)}
                </option>
              ))}
            </select>
          </label>

          {selectedDriver && (
            <div style={{
              background: '#f7f9fb',
              borderRadius: 9,
              padding: 12,
              display: 'grid',
              gap: 6,
              fontSize: 12,
              color: '#526174',
            }}>
              <b style={{ color: '#172033' }}>
                {selectedDriver.username}
              </b>

              <span>
                Телефон: {selectedDriver.phone || 'Не указан'}
              </span>

              <span>
                Филиал: {selectedDriver.branch_name || 'Не указан'}
              </span>

              <span>
                Рейтинг: {selectedDriver.rating}
              </span>

              <strong style={{
                color: '#b54708',
                fontSize: 15,
              }}>
                Текущий долг: {money(selectedDriver.cash_debt_kopecks)}
              </strong>
            </div>
          )}

          <label style={{
            display: 'grid',
            gap: 6,
            color: '#526174',
            fontSize: 12,
            fontWeight: 600,
          }}>
            Сумма погашения, ₽

            <input
              type="text"
              inputMode="decimal"
              value={amount}
              onChange={event => setAmount(event.target.value)}
              placeholder="Например, 500.00"
              required
              style={inputStyle}
            />
          </label>

          <label style={{
            display: 'grid',
            gap: 6,
            color: '#526174',
            fontSize: 12,
            fontWeight: 600,
          }}>
            Способ погашения

            <select
              value={paymentMethod}
              onChange={event => setPaymentMethod(
                event.target.value as 'cash' | 'driver_transfer',
              )}
              style={inputStyle}
            >
              <option value="cash">Наличные</option>
              <option value="driver_transfer">Перевод водителю</option>
            </select>
          </label>

          <button
            type="submit"
            disabled={!selectedDriver || submitting || loading}
            style={{
              ...primaryButtonStyle,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              opacity: !selectedDriver || submitting || loading
                ? 0.55
                : 1,
              cursor: !selectedDriver || submitting || loading
                ? 'not-allowed'
                : 'pointer',
            }}
          >
            <Wallet size={16} />
            {submitting
              ? 'Регистрируем погашение...'
              : 'Зарегистрировать погашение'}
          </button>
        </form>
      </div>

      <div style={cardStyle}>
        <h3 style={{
          margin: '0 0 12px',
          fontSize: 15,
          color: '#172033',
        }}>
          Задолженность водителей
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
            {drivers.map(driver => (
              <div
                key={driver.driver_user_id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 12,
                  flexWrap: 'wrap',
                  padding: '11px 0',
                  borderBottom: '1px solid #edf0f3',
                }}
              >
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
                  </span>
                </div>

                <strong style={{
                  color: driver.cash_debt_kopecks > 0
                    ? '#b54708'
                    : '#087e70',
                  fontSize: 14,
                }}>
                  {money(driver.cash_debt_kopecks)}
                </strong>
              </div>
            ))}
          </div>
        )}
      </div>

      <p style={{
        ...mutedStyle,
        lineHeight: 1.5,
        margin: 0,
      }}>
        Суммы и задолженности загружаются с сервера. Регистрация погашения
        создаёт финансовую запись и уменьшает долг водителя. Повторное
        изменение суммы на клиенте не позволяет обойти серверную проверку.
      </p>
    </section>
  );
}
