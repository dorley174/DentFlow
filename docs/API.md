# API DentFlow

В Dev Stand откройте http://localhost:8080/api/docs — это актуальная интерактивная схема, полученная из FastAPI. В production Swagger и OpenAPI публично отключены. Полная статическая спецификация находится в `docs/openapi.json`.

## Общие правила

- Все пути начинаются с `/api`. JSON, UTF-8, цены в копейках, даты ISO 8601 с часовым поясом.
- Для изменения данных обязательны `Content-Type: application/json` и `X-Requested-With: DentFlow`.
- Browser fetch использует `credentials: 'include'`. Сессионные токены хранятся в HttpOnly cookie, не в localStorage.
- При наличии `Origin` он должен точно входить в ALLOWED_ORIGINS. CORS wildcard запрещён в production.
- 401 — нужен вход; 403 — недостаточно прав; 404 — объект недоступен; 409 — конфликт записи или состояния; 422 — проверьте поля; 429 — повторите позже.
- Не передавайте tenant_id в обычных запросах кабинета: он берётся из серверной сессии. Непредусмотренные поля отклоняются.

## Сводка

| Методы и путь | Назначение |
|---|---|
| GET /health | Живость БД, а в production также Redis |
| GET /public/config | Окружение, доступность dev-инструментов, конфигурация тарифов |
| POST /auth/login; GET /auth/me; POST /auth/logout | Вход, текущий пользователь, выход |
| POST /public/demo/chat | Статический публичный пример без записи, пациентов и сохранения истории |
| POST /public/leads | Заявка клиники на подключение |
| GET /public/clinics/{slug} | Публичные сведения, врачи, услуги, филиалы |
| GET /public/clinics/{slug}/slots | Свободные интервалы для услуги и выбранной даты |
| POST /public/clinics/{slug}/appointments | Создание записи с согласием и ключом запроса |
| GET /public/clinics/{slug}/my-appointments | Только записи текущего пациента/сессии |
| PATCH /public/clinics/{slug}/appointments/{id} | Подтверждение, перенос или отмена своей записи |
| GET /public/clinics/{slug}/chat; POST .../chat | История и сообщения общего движка |
| GET .../notifications | Уведомления только текущего пациента |
| GET/PATCH .../consents | Настройки напоминаний и маркетинга |
| GET .../my-data; POST .../delete-my-data | Выгрузка и зарегистрированный запрос на удаление |
| POST .../telegram-link | Одноразовый код привязки Telegram к текущему профилю |
| GET /admin/bootstrap | Данные кабинета в пределах прав и tenant |
| GET/POST /admin/{resource}; PATCH /admin/{resource}/{id} | Справочники и CRM, разрешённые роли и поля |
| POST /admin/appointments; PATCH /admin/appointments/{id} | Ручная запись и изменение статуса |
| GET/PATCH /admin/settings | Настройки клиники и AI для владельца/управляющего |
| GET /admin/conversations/{id}/messages | История диалога клиники |
| PATCH /admin/conversations/{id}; POST .../messages | Перехват/возврат AI и ответ сотрудника |
| POST /admin/automations/run | Оценка автоматизаций; ускорение только Dev Stand |
| GET /super/overview; POST /super/tenants | Сводка платформы и создание клиники с владельцем |
| PATCH /super/tenants/{id}; PATCH /super/plans/{code} | Блокировка, тариф, цена и лимиты |
| POST /dev/simulate; POST /dev/reset | Только защищённые тестовые операции |

`resource`: branches, doctors, services, schedules, leads, tasks, employees, automation_rules. Для чтения также patients, appointments, conversations, notifications, integrations, audit_logs. Ответ списка: `items`; создание/обновление справочника: `item`. Специальные операции возвращают именованные объекты, например `appointment`.

## Пример записи

Сначала вызовите GET клиники и GET slots, чтобы взять реальные id и время. Не копируйте произвольные UUID или придуманный свободный интервал.

```json
{
  "service_id": "ID_ИЗ_СПРАВОЧНИКА",
  "doctor_id": "ID_ВРАЧА",
  "branch_id": "ID_ФИЛИАЛА",
  "start_at": "2026-11-10T10:00:00+03:00",
  "patient_name": "Тестовый Пациент",
  "phone": "+70000000001",
  "consent_pd": true,
  "consent_notifications": false,
  "idempotency_key": "unique-request-uuid"
}
```

Дата в примере иллюстративная: используйте фактический доступный будущий интервал. Повтор сетевого запроса должен сохранять idempotency_key; выбор нового времени — создавать новый ключ. Нельзя подтверждать интерфейсу успешную запись до ответа сервера.

Перенос:

```json
{"action": "reschedule", "start_at": "2026-11-11T11:00:00+03:00"}
```

Отмена:

```json
{"action": "cancel"}
```

## Инструменты движка

get_clinic_info/get_services/get_service_price/get_doctors реализованы через справочники клиники; get_available_slots — сервис расписания. create_appointment, reschedule_appointment, cancel_appointment и get_patient_appointments используют общий сервис записи и проверенную личность. create_lead/update_lead — CRM; request_human_assistance создаёт задачу и переводит диалог в human.

Это прикладные функции Python, а не публичный endpoint произвольного выполнения LLM-инструментов. Входящие действия доступны только через закрытый набор сценариев, Pydantic и проверки принадлежности объектов.

## Ограничения

Списки административного кабинета ограничены 2 000 строками на сущность; история чата — последними 100 сообщениями в ответе. Все сообщения хранятся до применения регламента удаления. Полнотекстовый поиск, пагинация больших наборов и отдельный отчётный контур — следующий этап. Данный API не является медицинской информационной системой обмена клиническими документами.
