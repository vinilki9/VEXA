
import React, { useCallback, useEffect, useState } from 'react';
import {
  Wallet,
  TrendingUp,
  Receipt,
  CreditCard,
  Banknote,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  FileSpreadsheet,
  Download,
  ArrowRightLeft,
} from 'lucide-react';

type MoneyValue = {
  kopecks: number;
  rub: number;
};

type FinanceSummary = {
  city: {
    code: string;
    name: string;
  };
  branch_id: string | null;
  period: {
    days: number;
    from: string;
    to: string;
    timezone: string;
  };
  completed_trips: number;
  total_trip_fare: MoneyValue;
  commission_accrued: MoneyValue;
  electronic_payments: {
    trip_fare_turnover: MoneyValue;
    commission: MoneyValue;
  };
  cash_payments: {
    trip_fare_turnover: MoneyValue;
    cash_trip_fare_turnover: MoneyValue;
    commission_debt_accrued: MoneyValue;
  };
  driver_transfer_payments: {
    trip_fare_turnover: MoneyValue;
  };
  debt_repayments: {
    total: MoneyValue;
    automatic_electronic_credit: MoneyValue;
    cash: MoneyValue;
    driver_transfer: MoneyValue;
  };
  current_driver_debt: MoneyValue;
  wallet_summary: {
    balance: MoneyValue;
    positive_balance: MoneyValue;
    reserved: MoneyValue;
    available: MoneyValue;
    negative_balance_debt: MoneyValue;
    drivers_with_negative_balance: number;
    drivers_count: number;
  };
  accounting_note: string;
};

type Props = {
  token: string;
  cityCode: string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

const cardStyle: React.CSSProperties = {
  background: 'var(--vexa-surface)',
  border: '1px solid #e8edf2',
  borderRadius: 12,
  padding: 17,
  minWidth: 0,
};

const mutedStyle: React.CSSProperties = {
  color: 'var(--vexa-text-secondary)',
  fontSize: 11,
};

const primaryButtonStyle: React.CSSProperties = {
  border: 0,
  borderRadius: 8,
  background: 'var(--vexa-primary)',
  color: 'var(--vexa-on-primary)',
  padding: '10px 14px',
  fontSize: 12,
  fontWeight: 700,
  cursor: 'pointer',
};

const selectStyle: React.CSSProperties = {
  height: 40,
  border: '1px solid #dfe6eb',
  borderRadius: 8,
  padding: '0 12px',
  background: 'var(--vexa-surface)',
  color: 'var(--vexa-text)',
  fontSize: 12,
  outline: 'none',
};

function money(value?: MoneyValue | null) {
  const amount = Number(value?.kopecks ?? 0) / 100;

  return `${amount.toLocaleString('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ₽`;
}

function formatDate(value?: string) {
  if (!value) return '—';

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return '—';

  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

async function requestSummary(
  token: string,
  cityCode: string,
  periodDays: number,
): Promise<FinanceSummary> {
  const response = await fetch(
    `${API_BASE}/api/v1/dispatch/finance/summary?city_code=${encodeURIComponent(cityCode)}&period_days=${periodDays}`,
    {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    },
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      data?.detail ||
      data?.message ||
      `Ошибка загрузки финансовой сводки: ${response.status}`,
    );
  }

  return data as FinanceSummary;
}

function localDateValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

async function downloadFinanceExport(
  token: string,
  cityCode: string,
  dateFrom: string,
  dateTo: string,
): Promise<void> {
  const params = new URLSearchParams({
    city_code: cityCode,
    date_from: dateFrom,
    date_to: dateTo,
  });

  const response = await fetch(
    `${API_BASE}/api/v1/dispatch/finance/export.xlsx?${params.toString()}`,
    {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(
      data?.detail ||
      data?.message ||
      `Ошибка экспорта Excel: ${response.status}`,
    );
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = `vexa_finance_${cityCode}_${dateFrom}_${dateTo}.xlsx`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}

function SummaryCard({
  title,
  value,
  description,
  icon,
  valueColor = 'var(--vexa-text)',
}: {
  title: string;
  value: string;
  description: string;
  icon: React.ReactNode;
  valueColor?: string;
}) {
  return (
    <article style={cardStyle}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 10,
      }}>
        <span style={{
          color: 'var(--vexa-text-secondary)',
          fontSize: 12,
          fontWeight: 600,
        }}>
          {title}
        </span>

        <span style={{
          width: 34,
          height: 34,
          display: 'grid',
          placeItems: 'center',
          borderRadius: 9,
          background: 'var(--vexa-primary-soft)',
          color: 'var(--vexa-primary)',
          flexShrink: 0,
        }}>
          {icon}
        </span>
      </div>

      <strong style={{
        display: 'block',
        marginTop: 13,
        fontSize: 23,
        lineHeight: 1.25,
        color: valueColor,
        overflowWrap: 'anywhere',
      }}>
        {value}
      </strong>

      <p style={{
        ...mutedStyle,
        margin: '7px 0 0',
        lineHeight: 1.5,
      }}>
        {description}
      </p>
    </article>
  );
}

function BreakdownRow({
  label,
  value,
  strong = false,
}: {
  label: string;
  value: string;
  strong?: boolean;
}) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: 12,
      padding: '11px 0',
      borderBottom: '1px solid #edf0f3',
    }}>
      <span style={{
        color: strong ? 'var(--vexa-text)' : 'var(--vexa-text-secondary)',
        fontSize: 12,
        fontWeight: strong ? 700 : 500,
      }}>
        {label}
      </span>

      <strong style={{
        color: 'var(--vexa-text)',
        fontSize: 12,
        textAlign: 'right',
        overflowWrap: 'anywhere',
      }}>
        {value}
      </strong>
    </div>
  );
}

export default function FinanceSummaryPanel({
  token,
  cityCode,
}: Props) {
  const [periodDays, setPeriodDays] = useState(30);
  const [exportDateFrom, setExportDateFrom] = useState(() => {
    const date = new Date();
    date.setDate(date.getDate() - 29);
    return localDateValue(date);
  });
  const [exportDateTo, setExportDateTo] = useState(() =>
    localDateValue(new Date()),
  );
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');

  const [summary, setSummary] = useState<FinanceSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [updatedAt, setUpdatedAt] = useState('');

  const loadSummary = useCallback(async () => {
    if (!token || !cityCode) return;

    setLoading(true);
    setError('');

    try {
      const result = await requestSummary(
        token,
        cityCode,
        periodDays,
      );

      setSummary(result);
      setUpdatedAt(new Date().toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
      }));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Не удалось загрузить финансовую сводку',
      );
    } finally {
      setLoading(false);
    }
  }, [token, cityCode, periodDays]);

  const handleExport = useCallback(async () => {
    if (!token || !cityCode) return;

    if (!exportDateFrom || !exportDateTo || exportDateFrom > exportDateTo) {
      setExportError('Проверьте даты начала и окончания отчёта');
      return;
    }

    setExporting(true);
    setExportError('');

    try {
      await downloadFinanceExport(
        token,
        cityCode,
        exportDateFrom,
        exportDateTo,
      );
    } catch (err) {
      setExportError(
        err instanceof Error
          ? err.message
          : 'Не удалось скачать финансовый отчёт',
      );
    } finally {
      setExporting(false);
    }
  }, [token, cityCode, exportDateFrom, exportDateTo]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  return (
    <section style={{
      display: 'grid',
      gap: 17,
      marginBottom: 24,
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 12,
      }}>
        <div>
          <p style={{
            ...mutedStyle,
            margin: 0,
            letterSpacing: 1,
            fontWeight: 700,
          }}>
            ФИНАНСОВЫЙ КОНТРОЛЬ
          </p>

          <h2 style={{
            color: 'var(--vexa-text)',
            fontSize: 20,
            margin: '5px 0 0',
          }}>
            Финансовая сводка
          </h2>

          <p style={{
            ...mutedStyle,
            margin: '5px 0 0',
          }}>
            {summary?.city.name || cityCode}
            {summary?.branch_id ? ' · Ваш филиал' : ' · Весь город'}
          </p>
        </div>

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 9,
          flexWrap: 'wrap',
        }}>
          <select
            value={periodDays}
            onChange={event => setPeriodDays(
              Number(event.target.value),
            )}
            style={selectStyle}
            aria-label="Период финансовой сводки"
          >
            <option value={7}>Последние 7 дней</option>
            <option value={30}>Последние 30 дней</option>
            <option value={90}>Последние 90 дней</option>
          </select>

          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            flexWrap: 'wrap',
            width: '100%',
            justifyContent: 'flex-end',
          }}>
            <label style={{ ...mutedStyle, display: 'grid', gap: 4 }}>
              С даты
              <input
                type="date"
                value={exportDateFrom}
                max={exportDateTo || undefined}
                onChange={event => setExportDateFrom(event.target.value)}
                style={selectStyle}
                aria-label="Начало периода экспорта"
              />
            </label>

            <label style={{ ...mutedStyle, display: 'grid', gap: 4 }}>
              По дату
              <input
                type="date"
                value={exportDateTo}
                min={exportDateFrom || undefined}
                max={localDateValue(new Date())}
                onChange={event => setExportDateTo(event.target.value)}
                style={selectStyle}
                aria-label="Окончание периода экспорта"
              />
            </label>

            <button
              type="button"
              onClick={handleExport}
              disabled={exporting || !token || !cityCode}
              style={{
                ...primaryButtonStyle,
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                opacity: exporting ? 0.6 : 1,
                background: '#176b55',
                alignSelf: 'end',
              }}
            >
              {exporting ? <Download size={14} /> : <FileSpreadsheet size={14} />}
              {exporting ? 'Формируем...' : 'Скачать Excel'}
            </button>
          </div>

          {exportError && (
            <div style={{
              color: 'var(--vexa-danger)',
              background: 'rgba(255, 133, 141, 0.12)',
              borderRadius: 8,
              padding: 10,
              fontSize: 12,
            }}>
              {exportError}
            </div>
          )}

          <button
            type="button"
            onClick={loadSummary}
            disabled={loading}
            style={{
              ...primaryButtonStyle,
              display: 'flex',
              alignItems: 'center',
              gap: 7,
              opacity: loading ? 0.6 : 1,
            }}
          >
            <RefreshCw
              size={14}
              style={{
                animation: loading
                  ? 'vexa-finance-spin 1s linear infinite'
                  : 'none',
              }}
            />
            Обновить
          </button>
        </div>
      </div>

      {error && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 9,
          color: 'var(--vexa-danger)',
          background: 'rgba(255, 133, 141, 0.12)',
          borderRadius: 9,
          padding: 12,
          fontSize: 12,
        }}>
          <AlertCircle size={17} />
          {error}
        </div>
      )}

      {summary && (
        <>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
            gap: 12,
          }}>
            <SummaryCard
              title="Начислено комиссии"
              value={money(summary.commission_accrued)}
              description={`${summary.completed_trips} завершённых поездок за период`}
              icon={<TrendingUp size={18} />}
              valueColor="#087e70"
            />

            <SummaryCard
              title="Текущий долг водителей"
              value={money(summary.wallet_summary.negative_balance_debt)}
              description={`${summary.wallet_summary.drivers_with_negative_balance} водителей с отрицательным балансом`}
              icon={<Wallet size={18} />}
              valueColor="#b54708"
            />

            <SummaryCard
              title="Доступно на кошельках"
              value={money(summary.wallet_summary.available)}
              description={`Зарезервировано: ${money(summary.wallet_summary.reserved)}`}
              icon={<Wallet size={18} />}
              valueColor="#087e70"
            />

            <SummaryCard
              title="Погашено автоматически"
              value={money(summary.debt_repayments.automatic_electronic_credit)}
              description="Часть электронных начислений, направленная на покрытие долга"
              icon={<CheckCircle2 size={18} />}
              valueColor="#087e70"
            />

            <SummaryCard
              title="Оборот поездок"
              value={money(summary.total_trip_fare)}
              description="Общая стоимость завершённых поездок"
              icon={<Receipt size={18} />}
            />
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: 12,
          }}>
            <div style={cardStyle}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 9,
                marginBottom: 7,
              }}>
                <CreditCard size={18} color="#15998d" />

                <h3 style={{
                  margin: 0,
                  color: 'var(--vexa-text)',
                  fontSize: 14,
                }}>
                  Электронные платежи
                </h3>
              </div>

              <BreakdownRow
                label="Оборот поездок"
                value={money(
                  summary.electronic_payments.trip_fare_turnover,
                )}
              />

              <BreakdownRow
                label="Комиссия сервиса"
                value={money(
                  summary.electronic_payments.commission,
                )}
                strong
              />

              <p style={{
                ...mutedStyle,
                lineHeight: 1.5,
                margin: '11px 0 0',
              }}>
                Банковские карты и СБП. Переводы пассажиров непосредственно водителям
                в эту категорию не входят.
              </p>
            </div>

            <div style={cardStyle}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 9,
                marginBottom: 7,
              }}>
                <Banknote size={18} color="#15998d" />

                <h3 style={{
                  margin: 0,
                  color: 'var(--vexa-text)',
                  fontSize: 14,
                }}>
                  Оплата водителю
                </h3>
              </div>

              <BreakdownRow
                label="Общий оборот"
                value={money(summary.cash_payments.trip_fare_turnover)}
                strong
              />

              <BreakdownRow
                label="Наличные"
                value={money(summary.cash_payments.cash_trip_fare_turnover)}
              />

              <BreakdownRow
                label="Перевод водителю"
                value={money(summary.driver_transfer_payments.trip_fare_turnover)}
              />

              <BreakdownRow
                label="Комиссия, начисленная в долг"
                value={money(
                  summary.cash_payments.commission_debt_accrued,
                )}
                strong
              />

              <p style={{
                ...mutedStyle,
                lineHeight: 1.5,
                margin: '11px 0 0',
              }}>
                Пассажир рассчитывается непосредственно с водителем.
                Комиссия VEXA списывается с кошелька водителя.
                При недостатке средств баланс становится отрицательным.
              </p>
            </div>

            <div style={cardStyle}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 9,
                marginBottom: 7,
              }}>
                <ArrowRightLeft size={18} color="#15998d" />

                <h3 style={{
                  margin: 0,
                  color: 'var(--vexa-text)',
                  fontSize: 14,
                }}>
                  Погашение задолженности
                </h3>
              </div>

              <BreakdownRow
                label="Всего погашено"
                value={money(summary.debt_repayments.total)}
                strong
              />

              <BreakdownRow
                label="Автоматически электронными начислениями"
                value={money(
                  summary.debt_repayments.automatic_electronic_credit,
                )}
              />

              <p style={{
                ...mutedStyle,
                lineHeight: 1.5,
                margin: '11px 0 0',
              }}>
                Электронные начисления сначала покрывают отрицательный
                баланс водителя. Наличные и переводы водителю не считаются
                отдельным погашением долга.
              </p>
            </div>

            <div style={cardStyle}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 9,
                marginBottom: 7,
              }}>
                <Wallet size={18} color="#15998d" />

                <h3 style={{
                  margin: 0,
                  color: 'var(--vexa-text)',
                  fontSize: 14,
                }}>
                  Состояние кошельков
                </h3>
              </div>

              <BreakdownRow
                label="Суммарный баланс"
                value={money(summary.wallet_summary.balance)}
                strong
              />

              <BreakdownRow
                label="Положительные балансы"
                value={money(summary.wallet_summary.positive_balance)}
              />

              <BreakdownRow
                label="Зарезервировано"
                value={money(summary.wallet_summary.reserved)}
              />

              <BreakdownRow
                label="Доступно"
                value={money(summary.wallet_summary.available)}
                strong
              />

              <BreakdownRow
                label="Водителей с кошельками"
                value={String(summary.wallet_summary.drivers_count)}
              />

              <p style={{
                ...mutedStyle,
                lineHeight: 1.5,
                margin: '11px 0 0',
              }}>
                Отрицательные балансы учитываются отдельно как задолженность
                водителей перед VEXA.
              </p>
            </div>
          </div>

          <div style={{
            ...cardStyle,
            background: 'var(--vexa-surface-2)',
          }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 10,
              flexWrap: 'wrap',
            }}>
              <div>
                <strong style={{
                  color: 'var(--vexa-text)',
                  fontSize: 12,
                }}>
                  Период отчёта
                </strong>

                <p style={{
                  ...mutedStyle,
                  margin: '5px 0 0',
                }}>
                  {formatDate(summary.period.from)}
                  {' — '}
                  {formatDate(summary.period.to)}
                </p>
              </div>

              <span style={mutedStyle}>
                Обновлено: {updatedAt || '—'}
              </span>
            </div>
          </div>

          <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 9,
            padding: 12,
            borderRadius: 9,
            background: '#fff8e8',
            color: '#805b16',
            fontSize: 11,
            lineHeight: 1.6,
          }}>
            <AlertCircle size={17} style={{ flexShrink: 0 }} />

            <span>
              {summary.accounting_note}
            </span>
          </div>
        </>
      )}

      {!summary && loading && (
        <div style={{
          ...cardStyle,
          color: 'var(--vexa-text-secondary)',
          textAlign: 'center',
          padding: 30,
        }}>
          Загружаем финансовую сводку...
        </div>
      )}

      <style>
        {`
          @keyframes vexa-finance-spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        `}
      </style>
    </section>
  );
}
