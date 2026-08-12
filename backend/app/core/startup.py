async def _bootstrap_admin_key() -> None:
    """
    Creates the first admin API key on the very first startup, if none
    exists yet. Uses ADMIN_BOOTSTRAP_KEY from env if set (so you control
    the actual key value); otherwise generates one and logs it ONCE -
    copy it immediately, it isn't stored in retrievable form afterward.
    """
    async with async_session_factory() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.is_admin == True)  # noqa: E712
        )

        # FIX:
        # Do not crash if multiple admin keys exist.
        # If at least one admin key already exists, simply return.
        existing_admin = result.scalars().first()

        if existing_admin is not None:
            return

    from app.config import settings
    import hashlib

    if settings.ADMIN_BOOTSTRAP_KEY:
        # Caller supplied the exact key via env - hash and store it directly
        # rather than going through issue_api_key (which generates a random one).
        async with async_session_factory() as session:
            from app.db.models import ApiKey as ApiKeyModel
            from datetime import datetime, timezone

            session.add(
                ApiKeyModel(
                    key_hash=hashlib.sha256(
                        settings.ADMIN_BOOTSTRAP_KEY.encode()
                    ).hexdigest(),
                    account_id=None,
                    is_admin=True,
                    label="bootstrap admin key (from ADMIN_BOOTSTRAP_KEY env)",
                    revoked=False,
                    created_at=datetime.now(timezone.utc),
                )
            )

            await session.commit()

        logger.info("Admin API key registered from ADMIN_BOOTSTRAP_KEY.")

    else:
        raw_key = await issue_api_key(
            account_id=None,
            is_admin=True,
            label="auto-generated bootstrap admin key",
        )

        logger.warning(
            "========================================\n"
            "No admin API key existed - generated one:\n"
            "  %s\n"
            "This is the ONLY time it will be shown in plaintext. Save it now\n"
            "(e.g. in a password manager) - it isn't recoverable from the DB.\n"
            "========================================",
            raw_key,
        )
