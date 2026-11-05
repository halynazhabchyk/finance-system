# Finance System

Навчальна мікросервісна система для керування особистими фінансами:
бюджетами, категоріями, витратами та звітами.

## Архітектура

Проєкт складається з трьох бізнес-мікросервісів та інфраструктурних
компонентів:

| Компонент | Призначення |
| --- | --- |
| **User Service** | Користувачі, автентифікація та внутрішній JWT |
| **Budget Service** | Бюджети, категорії, ліміти та витрати |
| **Report Service** | Місячні звіти та read model статистики |
| **Scheduler** | Публікація щоденних і щомісячних подій |
| **Traefik** | Єдина зовнішня точка входу та маршрутизація |
| **Consul** | Service Discovery і health checks |
| **RabbitMQ** | Асинхронна передача подій |
| **PostgreSQL** | Окрема база даних для кожного бізнес-сервісу |

Взаємодія між компонентами:

```text
Клієнт -> Traefik -> User / Budget / Report Service

Budget Service -- HTTP --> User Service
Budget Service -- події --> RabbitMQ --> Report Service
Scheduler -- події --> RabbitMQ --> Report Service

User Service    -> власна PostgreSQL база
Budget Service  -> власна PostgreSQL база
Report Service  -> власна PostgreSQL база та read model
```

Сервіси не звертаються напряму до баз даних один одного. Зовнішні HTTP-запити
проходять через Traefik, а екземпляри сервісів реєструються в Consul.

## Структура проєкту

```text
finance-system/
├── user_service/              # User Service
│   ├── app/
│   │   ├── api/               # dependencies і HTTP routers
│   │   ├── core/              # безпека
│   │   ├── db/                # сесія PostgreSQL
│   │   ├── models/            # SQLAlchemy-моделі UserAccount
│   │   ├── repositories/      # доступ до даних
│   │   ├── schemas/           # API-контракти
│   │   └── services/          # бізнес-логіка
│   ├── migrations/            # Alembic-міграції
│   └── tests/                 # API-тести
├── budget_service/            # Budget Service
│   ├── app/
│   │   ├── api/               # dependencies, routers, handlers
│   │   ├── db/                # сесія PostgreSQL
│   │   ├── integrations/      # публікація RabbitMQ-подій
│   │   ├── models/            # Budget, Category, Expense
│   │   ├── repositories/      # доступ до даних
│   │   └── services/          # бюджетні правила і сценарії
│   ├── migrations/
│   └── tests/
├── report_service/            # Report Service
│   ├── app/
│   │   ├── api/               # dependencies і routers
│   │   ├── db/                # сесія PostgreSQL
│   │   ├── models/            # read model і processed events
│   │   ├── repositories/      # робота з read model
│   │   ├── services/          # формування звітів
│   │   └── workers/           # RabbitMQ consumer
│   ├── migrations/
│   └── tests/
├── scheduler/                 # планувальник подій
│   └── app/
├── shared/                    # спільні контракти й інтеграції
│   ├── clients/               # HTTP-клієнти сервісів
│   ├── contracts/             # контракти подій
│   ├── messaging/             # RabbitMQ transport
│   ├── service_discovery/     # Consul integration
│   └── web/                   # спільні OpenAPI helpers
├── postgres/                  # створення окремих БД і ролей
├── traefik/                   # динамічна конфігурація Gateway
├── docker-compose.yml
├── run_tests.ps1
└── project.md
```

## Запуск локально

### 1. Підготовка змінних середовища

Створіть локальні файли `.env`, `user_service/.env`,
`budget_service/.env` і `report_service/.env` на основі параметрів
конфігурації. Вкажіть власні паролі та секрети. Ці файли не можна
додавати до Git.

Для захищених операцій встановіть однаковий `JWT_SECRET_KEY` довжиною
щонайменше 32 символи в `user_service/.env` і `budget_service/.env`.

### 2. Запуск усієї системи

У PowerShell виконайте:

```powershell
docker compose up --build
```

Основні локальні адреси:

| Адреса | Призначення |
| --- | --- |
| `http://localhost:8080` | Traefik Gateway |
| `http://localhost:8080/dashboard/` | Traefik Dashboard |
| `http://localhost:8500` | Consul UI |
| `http://localhost:15672` | RabbitMQ Management UI |
| `http://localhost:8010/docs` | Scheduler API |

### 3. API через Gateway

```text
/api/users/*        -> User Service
/api/users/auth/*   -> User Service authentication
/api/budgets/*      -> Budget Service
/api/reports/*      -> Report Service
```

Внутрішні маршрути сервісів доступні лише в Docker-мережі:

```text
User Service:   /internal/auth, /internal/users, /internal/health
Budget Service: /internal/budgets, /internal/health
Report Service: /internal/reports, /internal/health
```

### Міграції

Якщо сервіси запускаються не в контейнерах, застосуйте міграції окремо:

```powershell
& .\.venv\Scripts\alembic.exe -c .\user_service\alembic.ini upgrade head
& .\.venv\Scripts\alembic.exe -c .\budget_service\alembic.ini upgrade head
& .\.venv\Scripts\alembic.exe -c .\report_service\alembic.ini upgrade head
```

Скрипт `postgres/init-multiple-databases.sh` створює окремі бази даних для
User, Budget і Report Service під час першої ініціалізації Docker volume.

## Тестування

Для запуску наявних тестів використовуйте:

```powershell
.\run_tests.ps1
```

Тести розташовані в `tests/` кожного бізнес-сервісу. Результати виконання
тестів потрібно перевіряти фактично, а не вважати їх успішними лише після
запуску команди.

## Масштабування Budget Service

Щоб запустити три екземпляри Budget Service:

```powershell
docker compose up -d --build --scale budget-service=3 budget-service
docker compose ps budget-service
Invoke-RestMethod "http://localhost:8500/v1/health/service/budget-service?passing=true"
```

Екземпляри реєструються в Consul з різними ідентифікаторами, а Traefik
балансує запити між доступними екземплярами.

## Що не можна публікувати на GitHub

Не додавайте до репозиторію:

| Файл або папка | Причина |
| --- | --- |
| `.env` і `**/.env` | Паролі PostgreSQL/RabbitMQ, JWT та OAuth-секрети |
| `.venv/`, `venv/` | Локальне Python-оточення і встановлені залежності |
| `__pycache__/`, `*.pyc`, `.pytest_cache/` | Згенеровані кеш-файли Python і Pytest |
| `.mypy_cache/`, `.ruff_cache/`, `.coverage`, `htmlcov/` | Локальні результати перевірок |
| `*.log` | Логи, які можуть містити службові або персональні дані |
| `.idea/`, `.vscode/` | Персональні налаштування IDE, якщо вони не потрібні всій команді |
| `postgres_data/`, `rabbitmq_data/`, `consul_data/` | Локальні дані Docker volumes |
| Приватні ключі та сертифікати (`*.pem`, `*.key`, `*.crt`) | Секретні ключі доступу |
| `.agents/` | Локальні інструкції та службові матеріали середовища розробки |

Публікувати можна код, `requirements.txt`, Dockerfile, міграції,
`docker-compose.yml`, `traefik/dynamic.yml`, тести та приклади конфігурації
без реальних секретів. Перед першим `git add .` перевірте, що секрети не
потрапили до індексу Git.
