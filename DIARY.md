# Diário Técnico — Order Processing API

Registro completo das decisões, funcionalidades, estratégias e lições aprendidas durante o desenvolvimento deste projeto.

---

## Visão geral

API de processamento assíncrono de pedidos construída em Python 3.11+ com FastAPI, rodando em um único processo. O objetivo era demonstrar qualidade de código, separação de responsabilidades, uso correto de `async/await` e `asyncio.Queue`, validação de domínio com Pydantic v2, testes automatizados e rastreabilidade de estado.

---

## Estrutura de arquivos

```
order-processing/
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI, lifespan, endpoints
│   ├── models.py           # Pydantic v2, enums, validação de domínio
│   ├── repository.py       # Banco em memória encapsulado
│   ├── queues.py           # asyncio.Queue — singletons de módulo
│   ├── stock_service.py    # Worker de estoque
│   └── shipping_service.py # Worker de transporte
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # Fixtures compartilhadas, isolamento de estado
│   ├── test_models.py      # Testes unitários de validação
│   ├── test_api.py         # Testes de integração dos endpoints HTTP
│   └── test_workers.py     # Testes de comportamento assíncrono
├── .gitignore
├── pytest.ini
├── requirements.txt
├── README.md
└── DIARY.md                # este arquivo
```

---

## Funcionalidades implementadas

### 1. Criação de pedido — `POST /orders`

Recebe `customer_name` e uma lista de `items` (sku + quantity). Salva o pedido no repositório em memória com status `CREATED` e enfileira o ID na `stock_queue` para processamento assíncrono. Retorna `id`, `status` e `created_at`.

```json
// request
{ "customer_name": "João Silva", "items": [{ "sku": "ABC-123", "quantity": 2 }] }

// response 201
{ "id": "uuid", "status": "CREATED", "created_at": "2024-01-01T10:00:00Z" }
```

### 2. Consulta de pedido — `GET /orders/{order_id}`

Retorna o pedido completo com todos os campos, incluindo `status` atual, `created_at`, `updated_at` e a `timeline` completa. Retorna `404` se o ID não existir e `422` se o UUID for inválido.

### 3. Timeline de transições — `GET /orders/{order_id}/timeline`

Retorna a lista cronológica de todas as transições de status com seus timestamps exatos.

```json
[
  { "status": "CREATED",               "at": "2024-01-01T10:00:00.000Z" },
  { "status": "PROCESSING_STOCK",      "at": "2024-01-01T10:00:00.001Z" },
  { "status": "STOCK_RESERVED",        "at": "2024-01-01T10:00:01.002Z" },
  { "status": "PROCESSING_TRANSPORT",  "at": "2024-01-01T10:00:01.003Z" },
  { "status": "SENT_TO_TRANSPORT",     "at": "2024-01-01T10:00:02.004Z" }
]
```

### 4. Fluxo completo de status

```
CREATED
  → PROCESSING_STOCK       (worker de estoque inicia)
  → STOCK_RESERVED         (estoque separado com sucesso)
  → PROCESSING_TRANSPORT   (worker de transporte inicia)
  → SENT_TO_TRANSPORT      (pedido despachado)
  → FAILED                 (em caso de exceção em qualquer etapa)
```

Os status intermediários (`PROCESSING_STOCK`, `PROCESSING_TRANSPORT`) foram adicionados além do mínimo exigido — permitem observar o pedido em movimento em tempo real e demonstram visão de rastreabilidade.

---

## Decisões técnicas

### Um único processo Python

A especificação pedia simplicidade. Toda a aplicação roda no event loop do `asyncio`, sem Docker, broker externo ou banco de dados real. O `uvicorn` gerencia o event loop; `asyncio.create_task` sobe os workers dentro do mesmo loop.

### `asyncio.Queue` como fila interna

Escolha direta para filas em memória dentro de um único event loop. Garante ordenação FIFO, backpressure natural e integração limpa com `async/await`. A alternativa seria `threading.Queue`, mas ela bloquearia o event loop — incompatível com FastAPI assíncrono.

### `lifespan` ao invés de `@app.on_event`

`@app.on_event("startup")` está depreciado desde o FastAPI 0.93. O `lifespan` usa context manager assíncrono, é mais explícito sobre o ciclo startup/shutdown e garante que os workers são cancelados de forma limpa ao desligar a aplicação.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(stock_worker(), name="stock-worker"),
        asyncio.create_task(shipping_worker(), name="shipping-worker"),
    ]
    yield  # aplicação rodando
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
```

### Banco em memória com repositório encapsulado

O `dict[str, Order]` nunca é acessado diretamente — tudo passa pelo `OrderRepository`. Isso centraliza as operações de leitura e escrita, e facilita substituição por um banco real no futuro sem alterar os serviços.

### Imutabilidade com `model_copy`

O Pydantic v2 não permite mutação direta de campos por padrão. Em vez de `order.status = novo_status`, usamos `order.model_copy(update={...})` que retorna um novo objeto. Isso evita bugs sutis causados por mutação acidental de estado compartilhado.

### `utcnow()` com timezone explícito

```python
def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc).astimezone(ZoneInfo("America/Sao_Paulo"))
```

`datetime.utcnow()` retorna um objeto *naive* (sem timezone), o que causa ambiguidade ao serializar e comparar datas. Usar `datetime.now(tz=timezone.utc)` retorna um objeto *aware* — sempre com `+00:00` no output JSON, sem margem para interpretação errada. Inclui o zoneinfo no final para melhor compatilbilidade com o nosso timezone

### Injeção de filas nos workers

Os workers aceitam filas opcionais como parâmetro:

```python
async def stock_worker(
    in_queue: asyncio.Queue | None = None,
    out_queue: asyncio.Queue | None = None,
) -> None:
    source = in_queue if in_queue is not None else _queues.stock_queue
    ...
```
# Rever este ponto (_queue)
Em produção, usa as filas globais de módulo. Nos testes, recebe filas locais isoladas. Essa decisão surgiu de um problema real de vazamento de estado entre testes — e resolveu o problema de forma limpa sem precisar de mocks nas filas.

---

## Validação de domínio

A validação foi implementada em camadas no `models.py`, usando Pydantic v2.

### `OrderItem`

| Regra | Implementação |
|---|---|
| SKU normalizado para uppercase | `@field_validator("sku", mode="before")` com `.strip().upper()` |
| SKU não pode ser vazio ou só espaços | validador rejeita string em branco após normalização |
| SKU segue padrão alfanumérico com hífen | `Field(pattern=r"^[A-Z0-9][A-Z0-9\-]{1,29}$")` |
| Quantity deve ser positivo | `Field(gt=0)` |
| Quantity tem limite máximo | `Field(le=9999)` |

### `OrderCreate`

| Regra | Implementação |
|---|---|
| `customer_name` normalizado (strip) | `@field_validator("customer_name", mode="before")` |
| `customer_name` mínimo 2 caracteres | `Field(min_length=2)` |
| Lista de items não pode ser vazia | `Field(min_length=1)` |
| Máximo de 50 items por pedido | `Field(max_length=50)` |
| SKUs duplicados no mesmo pedido proibidos | `@model_validator(mode="after")` — valida o objeto completo após todos os campos serem processados |

A validação de SKUs duplicados usa `@model_validator` (nível do objeto) e não `@field_validator` (nível do campo) porque precisa comparar múltiplos items entre si — não é possível fazer isso olhando um campo isolado.

---

## Timestamps e rastreabilidade

### Campos adicionados ao `Order`

- `created_at` — momento exato da criação, nunca alterado
- `updated_at` — atualizado a cada transição de status
- `timeline` — lista de `StatusTransition(status, at)` acumulada a cada `update_status`

### Como a timeline é construída

No `create_order` do `main.py`, o pedido já nasce com a primeira transição:

```python
timeline=[StatusTransition(status=OrderStatus.CREATED, at=now)]
```

A cada chamada de `update_status` no repositório, uma nova transição é appended usando `model_copy`:

```python
self._store[str(order_id)] = order.model_copy(update={
    "status": status,
    "updated_at": now,
    "timeline": [*order.timeline, transition],  # spread + append
})
```

O spread `[*order.timeline, transition]` cria uma nova lista — não modifica a existente, mantendo a imutabilidade.

---

## Testes

### Estratégia geral

Três arquivos com responsabilidades distintas, seguindo o princípio de testar comportamento, não implementação.

### `test_models.py` — testes unitários puros

Testam as regras de negócio dos modelos sem nenhuma dependência externa. Rápidos, sem I/O, sem `async`. Cobrem os casos felizes e os casos de erro de cada validador.

Exemplos de casos testados:
- SKU em lowercase é normalizado para uppercase
- SKU com espaços é normalizado com strip
- SKU inválido (com espaço, muito curto) lança `ValidationError`
- Quantity zero ou negativo lança `ValidationError`
- `customer_name` em branco lança `ValidationError`
- Lista de items vazia lança `ValidationError`
- SKUs duplicados no mesmo pedido lançam `ValidationError`

### `test_api.py` — testes de integração HTTP

Usam `httpx.AsyncClient` com `ASGITransport` — sem servidor real, sem porta TCP. A app responde diretamente em memória, mas com o comportamento HTTP completo (status codes, headers, serialização JSON).

O fixture `client` ativa o **lifespan** da aplicação:

```python
async with app.router.lifespan_context(app):
    yield ac
```

Isso garante que os workers sobem e descem a cada teste, exatamente como em produção.

Exemplos de casos testados:
- `POST /orders` retorna 201 com `id`, `status` e `created_at`
- Pedido criado pode ser consultado em `GET /orders/{id}`
- `customer_name` em branco retorna 422
- Items vazio retorna 422
- SKUs duplicados retornam 422
- UUID inválido retorna 422
- ID inexistente retorna 404 com mensagem `"Order not found"`
- Timeline começa com `CREATED` e tem timestamps

### `test_workers.py` — testes de comportamento assíncrono

Testam os workers diretamente, sem passar pela API. Cada teste cria suas próprias filas `asyncio.Queue()` locais e as injeta nos workers — isso garante isolamento total entre testes sem depender de estado global.

Exemplos de casos testados:
- `process_stock` atualiza status para `STOCK_RESERVED`
- `process_stock` enfileira o ID na `transport_queue`
- `process_transport` atualiza status para `SENT_TO_TRANSPORT`
- Fluxo completo: pedido sai de `CREATED` e chega em `SENT_TO_TRANSPORT`
- Timeline ao final tem exatamente 5 transições na ordem correta
- Timestamps da timeline são monotonicamente crescentes
- Worker marca pedido como `FAILED` quando `process_stock` lança exceção
- Worker **não morre** após uma falha — continua processando o próximo pedido

### `conftest.py` — infraestrutura de teste

O fixture `reset_state` limpa o repositório em memória antes e depois de cada teste, garantindo isolamento. Usa `autouse=True` para ser aplicado automaticamente em todos os testes sem precisar declarar explicitamente.

```python
@pytest.fixture(autouse=True)
def reset_state():
    order_repository._store.clear()
    yield
    order_repository._store.clear()
```

---