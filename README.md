# CodeForge

Учебное веб-приложение с курсами, проверкой программ и закрытыми соревнованиями. Студент проходит теорию, тесты и практику. Преподаватель публикует материалы и выгружает ведомость. Администратор управляет ролями и блокировками.

## Локальный запуск с Judge0

Нужны Docker и Compose, OpenSSL, uv и отдельный Linux-стенд с cgroups v1 для Judge0 CE 1.13.1. Рекомендованная конфигурация стенда и результаты проверки приведены в [протоколе](documentation/verification.md).

```sh
sh scripts/setup.sh
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
uv run --locked pre-commit install
npm --prefix frontend ci
npm --prefix frontend run build
```

Pre-commit устанавливается один раз в каждой копии репозитория. Git хранит hook в `.git/hooks/pre-commit`. Для коммитов из IDE используйте ту же среду, где доступен `uv`.


Для интеграционных тестов укажите `CODEFORGE_TEST_URL=http://localhost:8080`, `CODEFORGE_TEST_ADMIN=admin@example.com`, `CODEFORGE_ADMIN_PASSWORD` и `CODEFORGE_DEMO_PASSWORD`. Запустите `uv run pytest -m integration` на тестовом Compose из предыдущего раздела.

## Языки Judge0

Один [каталог](app/codeforge/common/judge_languages.json) задаёт языки курса, шаблоны задачи и язык отправки в уроках и соревнованиях. CodeForge поддерживает Python 3, C++, C, C#, Go, Java, JavaScript, Pascal, PHP, Rust, TypeScript и SQL (SQLite) в [Judge0 CE 1.13.1](https://github.com/judge0/judge0/blob/v1.13.1/db/languages/active.rb). На каждый язык приходится одна версия среды исполнения. Ограничение действует в CodeForge и не меняет состав образа Judge0. Для Java и C# проверьте лимиты памяти и времени задачи.

Старые попытки остаются в истории. Если в задаче сохранились шаблоны удалённых языков, автор может скопировать их перед удалением и добавить поддерживаемый язык. В черновике соревнования повторно добавьте обновлённую задачу, чтобы заменить сохранённую версию.

CodeForge отправляет и опрашивает тесты пакетами до 20. Общий бюджет проверки учитывает число тестов, лимит запуска и компиляцию из стандартного Compose.

При редактировании задачи напрямую через API передайте полученную из `GET /api/edu/tasks/{id}` версию в заголовке `If-Match`. При конфликте версий сервер вернёт `409`.

## Judge0 на отдельном Droplet

Сайт и базы CodeForge остаются на первом Droplet. Второй запускает только Judge0 и его PostgreSQL и Redis. Разместите оба Droplet в одной VPC. Ограничьте входящий TCP 2358 на втором Droplet приватным IPv4 первого и привяжите порт к **приватному** IPv4 второго. Доменные записи и TLS сайта остаются на первом. Нужен Linux-хост с cgroups v1 для Judge0 CE 1.13.1.

На втором Droplet создайте отдельный `.env` с новыми случайными `JUDGE_DB_PASSWORD`, `JUDGE_REDIS_PASSWORD`, `JUDGE_SECRET` и `JUDGE_AUTH_TOKEN`. Например, каждое значение можно сгенерировать командой `openssl rand -hex 32`. Добавьте туда `JUDGE_PRIVATE_IP` и установите права `chmod 600 .env`. Пароли и ключи сайта этому хосту не нужны.

```sh
docker compose -p codeforge-judge -f compose.judge.yml -f compose.judge.host.yml build judge-server
docker compose -p codeforge-judge -f compose.judge.yml -f compose.judge.host.yml up -d --no-build
```

На первом Droplet добавьте в `.env` тот же `JUDGE_AUTH_TOKEN` и `JUDGE_URL=http://ПРИВАТНЫЙ_IP_JUDGE:2358`. Если в `.env` задан `COMPOSE_FILE`, замените `compose.judge.yml` на `compose.judge.remote.yml`. Сохраните действующее имя проекта и прежние параметры HTTPS.

```sh
docker compose -p codeforge -f compose.yml -f compose.judge.remote.yml up -d --build
```

Проверьте известным решением, что сайт получает `AC`. При переходе с Judge0 на том же хосте дождитесь завершения отправок и остановите прежние `judge-server`, `judge-sandbox`, `judge-db`, `judge-redis` через старый набор файлов Compose. Тома можно оставить для отката.

## Резервное копирование

Перед обновлением сохраните `.env`, `.local` и дампы PostgreSQL и MongoDB. Для согласованной копии сделайте снимок выключенного Droplet или временно остановите сервисы приложения и дождитесь остановки. Держите копию вне Droplet с доступом только для администратора. Приведённые команды используют работающие контейнеры баз.

```sh
umask 077
backup_dir=$(mktemp -d /var/tmp/codeforge-backup.XXXXXX)
docker compose exec -T postgres sh -c 'PGPASSWORD="$AUTH_PASSWORD" pg_dump -h 127.0.0.1 -U auth -Fc auth' > "$backup_dir/auth.dump"
docker compose exec -T postgres sh -c 'PGPASSWORD="$CONTEST_PASSWORD" pg_dump -h 127.0.0.1 -U contest -Fc contest' > "$backup_dir/contest.dump"
docker compose exec -T mongo mongodump --db education --archive --gzip > "$backup_dir/education.archive.gz"
tar -czf "$backup_dir/config.tar.gz" .env .local
printf '%s\n' "$backup_dir"
```

Проверяйте восстановление на отдельном проекте Compose с **пустыми** томами. Восстановите конфигурацию из архива в каталоге этого проекта, сохраните уникальное имя Compose-проекта и укажите каталог бэкапа в `backup_dir`. Поднимите базы отдельно от приложения, затем восстановите дампы.

```sh
docker compose up -d --wait postgres mongo
docker compose exec -T postgres sh -c 'PGPASSWORD="$AUTH_PASSWORD" pg_restore -h 127.0.0.1 -U auth -d auth --exit-on-error' < "$backup_dir/auth.dump"
docker compose exec -T postgres sh -c 'PGPASSWORD="$CONTEST_PASSWORD" pg_restore -h 127.0.0.1 -U contest -d contest --exit-on-error' < "$backup_dir/contest.dump"
docker compose exec -T mongo mongorestore --archive --gzip < "$backup_dir/education.archive.gz"
```

После запуска приложения проверьте вход, открытие курса и историю попыток. Служебные сессии Redis можно начать заново: браузер обновит access-токен через PostgreSQL либо попросит войти.

При обновлении сначала пересоберите все сервисы сайта в одной версии. Новый редактор отправляет `If-Match` для сохранения курса. После обновления старая вкладка редактора должна быть перезагружена. При откате к старому образу воркера завершите отправки на новых языках до переключения.

## Где читать код

- [Архитектура и контракты](documentation/architecture.md)
- [Протокол проверки и ограничения стенда](documentation/verification.md)
- [Граф Graphify](graphify-out/graph.html) и [отчёт](graphify-out/GRAPH_REPORT.md)
