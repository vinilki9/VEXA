# VEXA Legal by Role — 0.3.37

## Внесённые изменения
- `backend/app/legal_documents.py`: API каталога и отдельных версий документов для пяти ролей.
- `backend/app/legal_documents_catalog.json`: **неутверждённые черновики** по ролям Client / Driver / Navigator / Dispatcher / Admin.
- `backend/app/passenger_auth.py`: блокировка запроса SMS без обязательных подтверждений и сверка версии/хэша документа.
- `backend/app/auth_models.py` и Alembic 0019: снимок выбранных юридических подтверждений в сессии SMS.
- `android/client/app/.../PassengerAuthDialog.kt`: экран с отдельными галочками, открытием текста документа и отправкой выбранных подтверждений.
- `android/client/app/.../ApiClient.kt`: методы получения документов и передача подтверждений.
- `backend/tests/test_legal_documents.py`: 10 новых тестов.

## Проверено
- `python -m compileall -q app`: успешно.
- `pytest -q tests/test_legal_documents.py tests/test_legal_compliance.py tests/test_legal_dispatch_gate.py`: 24 пройденных теста.
- ZIP archive CRC: проверено.

## Не проверено / не завершено
- Компиляция Android APK и UI на устройстве.
- Интеграционный тест с PostgreSQL, SMS-провайдером и применением миграции.
- Экраны принятия документов в Driver, Navigator, Dispatcher, Admin: на данном этапе подготовлены **только серверные каталоги**.
- Документы нельзя публиковать как юридически действующие до рассмотрения юристом; **все имеют заголовок «ПРОЕКТ»**, отсутствуют реквизиты и утверждённые процессы.
- Перед коммерческим использованием необходим полноценный доказательственный аудит согласий и отзывов, внедрение согласий на обработку ПД для конкретных целей, где это требуется.

Выполнялось локально; VPS, GitHub, действующая БД не изменялись.
