# Нагрузочный тест поиска найденных вещей (BE-15)

Дата: 2026-11-08

**Требование (атрибут качества 2):** ответ GET /found-items ≤ 1.5 с на 20 000 записей.

## Окружение
- Машина: Apple M2, 8 ГБ RAM, macOS
- БД: PostgreSQL 17 (docker compose), приложение: uvicorn, 1 процесс, на той же машине
- Коммит: 94a8f15

## Данные
20 000 найденных вещей: `cd backend && python -m scripts.seed_found_items 20000` (seed 42).

## Сценарий
`backend/loadtest/locustfile.py`: 50 пользователей, набор 5/с, 3 минуты. Запросы к `GET /found-items`: по категории, текстовый, комбинированный фильтр, глубокая страница (offset до 19 000), limit=20. Токен каждый пользователь получает через `POST /dev-sso/token` (в таблицу не входит).

Запуск:

    cd backend
    SCHEDULER_ENABLED=false uvicorn app.main:app --port 8000
    locust -f loadtest/locustfile.py --host http://localhost:8000 --headless -u 50 -r 5 -t 3m --csv ../docs/loadtest/results --html ../docs/loadtest/report.html

## Результаты (мс)
| Запрос | Запросов | Ошибок | p50 | p95 | p99 |
|---|---|---|---|---|---|
| /found-items?category | 2336 | 0 | 10 | 18 | 40 |
| /found-items?combined | 1512 | 0 | 11 | 18 | 28 |
| /found-items?deep_offset | 732 | 0 | 17 | 32 | 45 |
| /found-items?q | 2328 | 0 | 31 | 43 | 62 |

Всего поисковых запросов: 6908, ошибок: 0.

## Вывод
Худший p95 среди поисковых запросов = **43 мс**, требование ≤ 1500 мс **выполнено**.

Полный отчёт: `docs/loadtest/report.html`, сырые данные: `docs/loadtest/results_*.csv`.
