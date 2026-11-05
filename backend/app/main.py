import json
import logging
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from .config import settings
from .errors import validation_message
from .db import engine
from .routers import public, admin, auth, system
from .public_demo import router as demo_router
from .telegram_links import router as telegram_router

logging.basicConfig(level=getattr(logging,settings.log_level.upper(),logging.INFO),
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger('dentflow')

app=FastAPI(title='DentFlow API',version='1.0.0',description='Административная платформа стоматологии. Все суммы в копейках.',
            docs_url='/api/docs' if settings.is_demo else None,
            openapi_url='/api/openapi.json' if settings.is_demo else None,
            redoc_url=None)
app.add_middleware(CORSMiddleware,allow_origins=settings.origins,allow_credentials=True,
                   allow_methods=['GET','POST','PATCH','DELETE','OPTIONS'],
                   allow_headers=['Content-Type','X-Requested-With'])

_rate=defaultdict(deque)
_rate_lock=threading.Lock()
_redis=None
if settings.redis_url:
    from redis import Redis
    _redis=Redis.from_url(settings.redis_url,socket_connect_timeout=2,socket_timeout=2)


def rate_limit(key,limit,window=60):
    if settings.app_env=='test':
        return True
    now=time.time()
    if _redis:
        # Lua atomically increments AND sets expiry; interrupted workers cannot leave immortal keys.
        script="local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]); end; return n"
        try:
            n=_redis.eval(script,1,'dentflow:rate:'+key,str(window))
            return n<=limit
        except Exception:
            if settings.app_env=='production':
                raise HTTPException(503,'Сервис временно недоступен. Повторите позже.')
    with _rate_lock:
        queue=_rate[key]
        while queue and queue[0]<now-window:
            queue.popleft()
        if len(queue)>=limit:
            return False
        queue.append(now)
        # Bound memory for an internet-facing development server.
        if len(_rate)>10000:
            for stale in [k for k,v in _rate.items() if not v or v[-1]<now-window]:
                _rate.pop(stale,None)
        return True


@app.middleware('http')
async def request_guard(request:Request,call_next):
    path=request.url.path
    if request.method=='OPTIONS':
        return await call_next(request)
    if path.startswith('/api/') and request.method not in {'GET','HEAD'}:
        if request.headers.get('X-Requested-With')!='DentFlow':
            return JSONResponse({'detail':'Запрос отклонён: отсутствует защитный заголовок'},status_code=403)
        origin=request.headers.get('Origin')
        if origin and origin.rstrip('/') not in settings.origins:
            return JSONResponse({'detail':'Запрос с этого сайта не разрешён'},status_code=403)
        if request.headers.get('content-type','').split(';')[0].strip().lower()!='application/json':
            return JSONResponse({'detail':'Ожидается JSON-запрос'},status_code=415)
        try:
            length=int(request.headers.get('content-length','0'))
        except ValueError:
            return JSONResponse({'detail':'Некорректный размер запроса'},status_code=400)
        if length>65536:
            return JSONResponse({'detail':'Запрос слишком большой'},status_code=413)
        body=await request.body()
        if len(body)>65536:
            return JSONResponse({'detail':'Запрос слишком большой'},status_code=413)
    if path.startswith('/api/public/') or path=='/api/auth/login':
        ip=request.client.host if request.client else 'unknown'
        category='login' if path=='/api/auth/login' else 'public'
        try:
            allowed=rate_limit(category+':'+ip,20 if category=='login' else 240)
        except HTTPException as exc:
            return JSONResponse({'detail':exc.detail},status_code=exc.status_code)
        if not allowed:
            return JSONResponse({'detail':'Слишком много запросов. Повторите через минуту.'},status_code=429,headers={'Retry-After':'60'})
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    if path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'
    return response


@app.exception_handler(RequestValidationError)
async def invalid_input(request,exc):
    return JSONResponse(status_code=422,content={'detail':'Проверьте заполненные поля',
        'errors':[{'field':'.'.join(str(x) for x in err['loc'][1:]),'message':validation_message(err)} for err in exc.errors()]})


@app.exception_handler(IntegrityError)
async def integrity_error(request,exc):
    # Never expose raw SQL, patient data, or constraint payload to a client.
    return JSONResponse(status_code=409,content={'detail':'Данные конфликтуют с существующей записью. Возможно, время занято или такой объект уже существует.'})


@app.get('/health')
@app.get('/api/health',tags=['Диагностика'])
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        if settings.app_env=='production':
            if not _redis or not _redis.ping():
                raise RuntimeError('redis unavailable')
    except Exception:
        raise HTTPException(503,'База данных или очередь временно недоступна')
    return {'status':'ok','environment':settings.app_env,'version':'1.0.0'}


app.include_router(auth.router)
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(system.router)
app.include_router(demo_router)
app.include_router(telegram_router)
