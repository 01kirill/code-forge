# CodeForge

Учебное веб-приложение с курсами, проверкой программ и закрытыми соревнованиями. Студент проходит теорию, тесты и практику. Преподаватель публикует материалы и выгружает ведомость. Администратор управляет ролями и блокировками.

## Локальный запуск с Judge0

Нужны Docker и Compose, OpenSSL, uv и отдельный Linux-стенд с cgroups v1 для Judge0 CE 1.13.1. Рекомендованная конфигурация стенда и результаты проверки приведены в [протоколе](documentation/verification.md).

```sh
./scripts/setup.sh
docker compose -f compose.yml -f compose.judge.yml up -d --build
docker compose exec auth python -m codeforge.auth.bootstrap \
  --name site_admin --email admin@example.com
```

Откройте [https://localhost:8443](https://localhost:8443). Скрипт создаёт локальный сертификат с SAN для localhost и 127.0.0.1. Доверенный сертификат стенда можно положить в `.local/tls/cert.pem` и `.local/tls/key.pem` перед запуском nginx. При установке для команды оставьте включённым `Secure` для cookie и укажите адрес привязки в `CODEFORGE_BIND`. HTTP-порт всегда ограничен loopback. Если npm недоступен из сети сборщика Docker, на локальном Linux запуск можно повторить с `CODEFORGE_BUILD_NETWORK=host`.

Подготовить учебные данные можно с uv и учётной записью администратора. Задайте переменные `CODEFORGE_ADMIN_PASSWORD` и `CODEFORGE_DEMO_PASSWORD` в окружении. Для HTTPS укажите путь к сертификату в `SSL_CERT_FILE`. Скрипт создаёт `teacher@example.com`, `author2@example.com`, `student1@example.com` и `student2@example.com` с выбранным демонстрационным паролем.

```sh
uv sync --locked
SSL_CERT_FILE=.local/tls/cert.pem uv run python scripts/seed_demo.py \
  --url https://localhost:8443 --admin admin@example.com
```

Для локального тестового стенда без поддержки Judge0 используйте отдельный проект Compose с имитацией API проверки. Она возвращает заданные ответы на тестовые строки и не запускает отправленные программы.

```sh
SECURE_COOKIE=false docker compose -p codeforge-test -f compose.yml \
  -f compose.test.yml up -d --build
docker compose -p codeforge-test exec auth python -m codeforge.auth.bootstrap \
  --name site_admin --email admin@example.com
uv run python scripts/seed_demo.py --admin admin@example.com
```

В тестовом режиме браузер открывает [http://localhost:8080](http://localhost:8080). При параллельном запуске двух стендов задайте свободные `CODEFORGE_PORT` и `CODEFORGE_DEV_PORT`.

Чтобы запустить этот тестовый стенд на VPS и открыть HTTPS снаружи, используйте полную команду из каталога проекта.

```sh
CODEFORGE_BIND=0.0.0.0 docker compose -p codeforge-test -f compose.yml \
  -f compose.test.yml up -d --build
```

`CODEFORGE_BIND` задаёт адрес привязки HTTPS (по умолчанию порт 8443). Два `-f` объединяют базовую конфигурацию и тестовую подмену Judge0. `-p codeforge-test` даёт стенду отдельное имя. `up -d --build` собирает образы и запускает весь стенд в фоне. Если дописать `gateway`, Compose запустит только nginx, так как он не объявляет зависимости от API и других сервисов.

Чтобы остановить и удалить контейнеры этого стенда, укажите то же имя и файлы.

```sh
docker compose -p codeforge-test -f compose.yml -f compose.test.yml down
```

## Проверки

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -m 'not integration'
uv run pre-commit install
npm --prefix frontend ci
npm --prefix frontend run build
```

Для интеграционных тестов укажите `CODEFORGE_TEST_URL=http://localhost:8080`, `CODEFORGE_TEST_ADMIN=admin@example.com`, `CODEFORGE_ADMIN_PASSWORD` и `CODEFORGE_DEMO_PASSWORD`. Запустите `uv run pytest -m integration` на тестовом Compose из предыдущего раздела.

## Где читать код

- [Архитектура и контракты](documentation/architecture.md)
- [Протокол проверки и ограничения стенда](documentation/verification.md)
- [Граф Graphify](graphify-out/graph.html) и [отчёт](graphify-out/GRAPH_REPORT.md)
