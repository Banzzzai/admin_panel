
🔴 1. Часть роутов возвращает HTML, а не JSON:
# router_activity.py
return templates.TemplateResponse("activity.html", {...})
# router_gis.py  — POST/PUT/DELETE
return flash_success(request, f"Воркспейс «{workspace_id}» создан.", "/gis/workspaces/")
# ^ это RedirectResponse 303, не JSON!
# router_users.py  — POST edit/delete
return RedirectResponse(url="/auth/users", status_code=303)
То есть бэкендер делал SSR-админку на Jinja2, а не API для React. Для React это означает:
GET-списки — часть отдаёт JSON (/gis/workspaces/{id}, /gis/product-sets/{id}), а часть — HTML (/gis/workspaces/ возвращает TemplateResponse). Это сломает твою админку.
POST/PUT/DELETE — возвращают 303 Redirect на HTML-страницу. React-форма получит редирект вместо JSON-ответа.


🟡 2. Flash-сообщения через сессию — не для React
flash_error / flash_success кладут сообщение в request.session и редиректят. React так не работает — тебе нужен JSON-ответ:

json
{ "ok": true, "message": "Воркспейс создан" }
или

json
{ "ok": false, "error": "Заполните workspace_id" }
🟡 3. router_users.py ходит напрямую в Keycloak Admin API

Токен кешируется в памяти процесса (_admin_token_cache) — при нескольких воркерах uvicorn будет рассинхрон. Для админки с одним воркером ок.
Список пользователей идёт с max=500 — если больше 500, часть потеряется. Нужна пагинация.

🟡 4. Список пользователей делает N+1 запросов в Keycloak
python
for u in kc_users:
    r_ur = await kc_request("GET", f"/users/{u['id']}/role-mappings/realm")
На 500 юзеров — 500 запросов к Keycloak. Медленно. Это проблема бэка, но ты её почувствуешь как долгую загрузку страницы «Пользователи».

🟡 5. POST /workspaces/ без _method=PUT — как обновлять?
В router_gis.py на один и тот же путь /workspaces/{id} есть и PUT, и DELETE. Из React это ок (можно fetch с нужным методом). Но бэкендер в HTML-формах использует MethodOverrideMiddleware — значит, в реальности браузер шлёт POST с _method. Для React это не нужно, но надо убедиться, что реальные PUT/DELETE работают (CORS middleware пропускает все методы — ок).

🟡 6. CORS allow_origins=["*"] + allow_credentials=True
Это невалидная комбинация по спецификации CORS. Браузер может отклонить запросы с credentials: 'include'. Тебе нужно, чтобы бэкендер явно указал origin твоей админки:

python
allow_origins=["http://10.13.7.30:3000", "http://localhost:5173"],
Иначе cookie-based авторизация может не работать из React.

Вот сводка — что можно использовать уже сейчас без переделок:

Метод	Путь	Ответ	Комментарий
GET	/gis/workspaces/{id}	JSON ✅	один воркспейс
GET	/gis/product-sets/{id}	JSON ✅	один product_set
GET	/gis/products/{id}	JSON ✅	один продукт
GET	/gis/layer-chunks/{id}	JSON ✅	один чанк
GET	/gis/workspaces/	HTML ❌	переделать на JSON
GET	/gis/product-sets/	HTML ❌	переделать
GET	/gis/products/	HTML ❌	переделать
GET	/gis/layer-chunks/	HTML ❌	переделать
POST/PUT/DELETE	/gis/...	303 redirect ❌	переделать на JSON
GET	/auth/users/	HTML ❌	Keycloak-юзеры
POST	/auth/users/edit/{id}	303 ❌	
GET	/auth/users/delete/{id}	303 ❌	⚠️ GET на удаление — плохо
GET	/auth/audit/	HTML ❌	аудит-лог
GET	/auth/activity/	HTML ❌	активность
GET	/auth/logs/	HTML ❌	логи из файла
GET	/activity/heartbeat	204 ✅	не нужно тебе