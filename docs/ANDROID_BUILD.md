# Сборка Android

Требуется Android Studio актуальной стабильной версии, Android SDK и JDK 17.

## Клиент
Откройте `android/client` в Android Studio и дождитесь синхронизации Gradle.
```bash
gradle assembleDebug
```
Ожидаемый debug APK: `app/build/outputs/apk/debug/app-debug.apk`.

## Водитель
Откройте `android/driver`.
```bash
gradle assembleDebug
```

## Release
Release-сборка требует keystore организации и настройки signing config. Не помещайте keystore и пароли в репозиторий и не отправляйте их в чат. Подпись должна выполняться на доверенной машине владельца проекта.

Этот пакет содержит исходники и Gradle-конфигурацию, но не содержит Gradle Wrapper и готовых APK. Если локальный Gradle не установлен, Android Studio может использовать встроенный механизм сборки после импорта проекта.
