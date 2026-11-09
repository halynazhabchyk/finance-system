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
Budget Service записує події в таблицю `outbox_events` у тій самій транзакції,
що й бізнес-зміну, а `OutboxPublisher` публікує їх у RabbitMQ: `BudgetCreated`,
`BudgetUpdated` (зокрема зміни категорій), `BudgetDeleted`, `ExpenseCreated`,
`ExpenseUpdated`, `ExpenseDeleted`, `ExpenseCancelled` (компенсація SAGA).
Кожна подія містить snapshot бюджету та версію агрегату, тому Report Service
ігнорує застарілі snapshots. Scheduler публікує `DailyReportUpdateRequested` або
`MonthlyReportUpdateRequested` із конкретним періодом.

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
/api/assistant/*    -> AI Assistant (ЛР №4)
/mcp                -> MCP Server, Streamable HTTP (ЛР №4)
/agents/budget/*    -> budget-agent, A2A (ЛР №4)
/agents/report/*    -> report-agent, A2A (ЛР №4)
```

Внутрішні маршрути сервісів доступні лише в Docker-мережі:

```text
User Service:   /internal/auth, /internal/users, /internal/health
Budget Service: /internal/budgets, /internal/health
Report Service: /internal/reports/monthly/{year}/{month},
                /internal/reports/annual/{year}, /internal/health
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

## Transactional Outbox, Inbox і SAGA (ЛР №3)

Розподілена операція «створення витрати» реалізована як SAGA-хореографія:

```text
T1  Budget Service : expense PENDING + saga_instances STARTED + outbox ExpenseCreated
T2  Report Service : read model + processed_events (Inbox) -> ExpenseProcessed
OK  Budget Service : saga COMPLETED, expense CONFIRMED
CT1 Budget Service : expense CANCELLED + saga CANCELLED + outbox ExpenseCancelled
CT2 Report Service : застосовує новіший snapshot ExpenseCancelled
```

Компенсацію запускають `SagaDlqConsumer` (повідомлення в DLQ) або
`SagaTimeoutWatcher` (немає відповіді до `deadline_at`).

| Черга | Exchange / routing key | Споживач |
| --- | --- | --- |
| `report-service-events` | `finance.events` / події Budget і Scheduler | Report Service |
| `report-service-events.retry`, `.dlq` | `finance.events.retry`, `finance.events.dlx` / `#` | повтори та DLQ Report Service |
| `budget-service-saga-events` | `finance.events` / `ExpenseProcessed` | `SagaReplyConsumer` |
| `budget-service-saga-dlq` | `finance.events.dlx` / `ExpenseCreated` | `SagaDlqConsumer` |

| Змінна | Сервіс | За замовчуванням |
| --- | --- | --- |
| `OUTBOX_POLL_INTERVAL` | Budget | `2` с |
| `OUTBOX_SIMULATE_FAILURE` | Budget | `false` |
| `SAGA_TIMEOUT_SECONDS` | Budget | `30` с |
| `SAGA_WATCH_INTERVAL` | Budget | `5` с |
| `RABBITMQ_MAX_DELIVERY_ATTEMPTS` | Report | `3` |
| `RABBITMQ_RETRY_DELAY_SECONDS` | Budget, Report | `5` с |
| `REPORT_SIMULATE_FAILURE` | Report | `false` |

Увімкнення імітації збою консьюмера (PowerShell):

```powershell
$env:REPORT_SIMULATE_FAILURE = "true"
docker compose up -d report-service
```

Стан SAGA витрати: `GET /api/budgets/{budget_id}/expenses/{expense_id}/saga`.

## AI-агенти: function calling, MCP, A2A (ЛР №4)

Компоненти звертаються до системи лише через Traefik із JWT користувача,
власних БД не мають. Спільний код – `shared/ai_tools/`.

| Компонент | Папка | Gateway |
| --- | --- | --- |
| AI Assistant | `ai_assistant/` | `POST /api/assistant/chat`, Swagger `/api/assistant/docs` |
| MCP Server | `mcp_server/` | `/mcp` (Streamable HTTP); локально – stdio |
| budget-agent | `budget_agent/` | `/agents/budget/.well-known/agent-card.json` |
| report-agent | `report_agent/` | `/agents/report/.well-known/agent-card.json` |
| Інтерактивний A2A-клієнт | `a2a_chat/` | консольна програма, не сервіс: чат з агентом природною мовою |

Потрібна змінна в кореневому `.env`: `LLM_API_KEY` (ключ Google Gemini).
Необов'язкові: `LLM_MODEL` (за замовчуванням `gemini-3.5-flash`) і `LLM_THINKING_LEVEL`.

```powershell
# JWT користувача
$token = (Invoke-RestMethod -Method Post http://localhost:8080/api/users/auth/login `
  -ContentType "application/x-www-form-urlencoded" -Body "username=<email>&password=<password>").access_token

# Запит до асистента
Invoke-RestMethod -Method Post http://localhost:8080/api/assistant/chat -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" -Body '{"message": "Скільки я ще можу витратити на розваги в листопаді 2026?"}'

# MCP Inspector: stdio (з кореня проєкту) або HTTP http://localhost:8080/mcp
$env:MCP_USER_JWT = $token; $env:GATEWAY_URL = "http://localhost:8080"
npx @modelcontextprotocol/inspector .\.venv\Scripts\python.exe mcp_server\app\main.py

# Чат з A2A-агентом природною мовою
.\.venv\Scripts\python.exe -m a2a_chat                  # budget-agent (producer)
.\.venv\Scripts\python.exe -m a2a_chat --agent report   # report-agent (consumer)
```
