class Order(Base):
    __tablename__ = "orders"

    __table_args__ = (
        UniqueConstraint(
            "city_id",
            "idempotency_key",
            name="uq_orders_city_idempotency",
        ),
        UniqueConstraint(
            "public_number",
            name="uq_orders_public_number",
        ),
        CheckConstraint(
            "price_rub IS NULL OR price_rub >= 0",
            name="orders_price_rub_nonnegative",
        ),
        CheckConstraint(
            "price_kopecks IS NULL OR price_kopecks >= 0",
            name="orders_price_kopecks_nonnegative",
        ),
        Index(
            "ix_orders_city_status_created",
            "city_id",
            "status",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )
    public_number: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cities.id"),
        nullable=False,
        index=True,
    )
    tariff_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tariffs.id"),
        nullable=True,
        index=True,
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("branches.id"),
        nullable=True,
        index=True,
    )
    passenger_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("passenger_profiles.user_id"),
    )
    driver_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("driver_profiles.user_id"),
        index=True,
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicles.id"),
    )

    customer_name: Mapped[str | None] = mapped_column(String(120))
    customer_phone: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    anonymous: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    pickup_address: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    destination_address: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    pickup_latitude: Mapped[float | None] = mapped_column(Float)
    pickup_longitude: Mapped[float | None] = mapped_column(Float)
    destination_latitude: Mapped[float | None] = mapped_column(Float)
    destination_longitude: Mapped[float | None] = mapped_column(Float)

    status: Mapped[str] = mapped_column(
        String(40),
        default="new",
        nullable=False,
        index=True,
    )
    payment_method: Mapped[str] = mapped_column(
        String(30),
        default="cash",
        nullable=False,
    )

    price_rub: Mapped[int | None] = mapped_column(Integer)
    price_kopecks: Mapped[int | None] = mapped_column(Integer)

    comment: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
        nullable=False,
    )
