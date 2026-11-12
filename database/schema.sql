CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE branches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  name TEXT NOT NULL,
  city_code TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id)
);
CREATE TABLE tariff_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  branch_id UUID REFERENCES branches(id),
  city_group TEXT NOT NULL,
  tariff_code TEXT NOT NULL,
  base_kopecks BIGINT NOT NULL CHECK (base_kopecks >= 0),
  included_minutes INTEGER NOT NULL DEFAULT 0,
  included_meters INTEGER NOT NULL DEFAULT 0,
  per_km_kopecks BIGINT NOT NULL CHECK (per_km_kopecks >= 0),
  per_minute_kopecks BIGINT NOT NULL CHECK (per_minute_kopecks >= 0),
  effective_from TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  branch_id UUID NOT NULL REFERENCES branches(id),
  passenger_phone TEXT NOT NULL,
  pickup_text TEXT NOT NULL,
  destination_text TEXT NOT NULL,
  tariff_snapshot JSONB NOT NULL,
  fare_kopecks BIGINT CHECK (fare_kopecks >= 0),
  payment_method TEXT NOT NULL CHECK (payment_method IN ('cash','driver_transfer','card','sbp')),
  status TEXT NOT NULL DEFAULT 'new',
  driver_id UUID,
  idempotency_key TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  UNIQUE (organization_id, idempotency_key)
);
CREATE INDEX orders_branch_status_idx ON orders(branch_id, status, created_at DESC);
CREATE TABLE audit_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  branch_id UUID REFERENCES branches(id),
  actor_id UUID,
  event_type TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id UUID NOT NULL,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Production: add strict FK constraints for drivers/passengers, RLS policies,
-- role grants, retention policy and Alembic migrations before deployment.
